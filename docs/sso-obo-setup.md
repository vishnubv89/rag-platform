# SSO + ServiceNow OBO Setup Guide

This document walks through configuring Zitadel as the identity provider and
enabling On-Behalf-Of (OBO) token exchange with ServiceNow so the retrieval
layer uses the signed-in user's ServiceNow permissions rather than a shared
service account.

---

## Architecture

```
User browser
  │  (1) Sign in via Zitadel OIDC
  ▼
Knowledge Mesh frontend
  │  (2) Sends Zitadel access token in Authorization header
  ▼
Knowledge Mesh backend  ──────── (3) validates token via Zitadel JWKS
  │
  │  (4) Exchanges Zitadel token for ServiceNow token (RFC 8693)
  ▼
ServiceNow KB API  ──── returns only articles the user can see (ACL-filtered)
  │
  ▼  merged with pgvector results
Knowledge Mesh retriever → grader → generator
```

---

## Part 1 — Start Zitadel

Zitadel is included in `docker-compose.yml`.  Start it alongside the rest of
the stack:

```bash
docker compose up -d
```

On first boot (~30 s) Zitadel creates a `zitadel` database inside the
existing postgres container and writes the initial admin user.

**Admin UI:** http://localhost:8088  
**Default credentials:**
```
Username: zitadel-admin@zitadel.localhost
Password: Password1!
```

> Change these immediately in production.

---

## Part 2 — Configure Zitadel

### 2.1 Create an application

1. Log in to http://localhost:8088.
2. In the default organisation, go to **Projects → Create Project**.
   Name it `KnowledgeMesh`.
3. Inside the project, click **New Application**.
   - Type: **Web** (for the frontend) or **API** (for M2M/backend).
   - Name: `Frontend`.
   - Auth method: `PKCE` (for SPA frontend) or `JWT` (for API).
4. Copy the **Client ID** — you'll need it in the frontend `.env`.
5. Under **Token Settings**, enable:
   - `User Info inside ID Token`
   - `Include granted roles in token`

### 2.2 Add custom claim for org_id (optional)

To route Zitadel users into specific Knowledge Mesh organisations, add an
action that injects a `knowledge_mesh_org_id` claim into the token:

1. Go to **Actions → New Action**.
2. Name: `inject_org_id`, trigger: `Pre Userinfo Creation`.
3. Script:
   ```js
   function setOrgId(ctx, api) {
     // Map Zitadel org IDs or email domains to Knowledge Mesh org IDs
     const orgMap = { "org-1-zitadel-id": 3 };
     const orgId = orgMap[ctx.org.id] || null;
     if (orgId) api.v1.claims.setClaim("knowledge_mesh_org_id", orgId);
   }
   ```
4. Assign the action to **Complements**.

Without this action, Zitadel users land in `org_id = null` (default org).

### 2.3 Point the backend at Zitadel

Add to `.env`:

```bash
ZITADEL_ISSUER=http://localhost:8088
```

Restart the backend:

```bash
docker compose restart backend
```

Verify the OIDC discovery endpoint:

```bash
curl http://localhost:8088/.well-known/openid-configuration | jq .issuer
# should print: "http://localhost:8088"
```

---

## Part 3 — Configure ServiceNow for OBO

### 3.1 Register an OAuth 2.0 application in ServiceNow

1. In ServiceNow, navigate to **System OAuth → Application Registry**.
2. Click **New → Create an OAuth API endpoint for external clients**.
3. Fill in:

   | Field | Value |
   |---|---|
   | Name | `KnowledgeMesh OBO` |
   | Client ID | (auto-generated — copy this) |
   | Client Secret | (auto-generated — copy this) |
   | Redirect URL | `http://localhost:8088/oauth/v2/authorize` |

4. Save the record and note the **Client ID** and **Client Secret**.

### 3.2 Enable Token Exchange grant type

Token Exchange (RFC 8693) is not enabled by default in older ServiceNow
releases.  To enable it:

1. Navigate to **System OAuth → OAuth Token Exchange Policy**.
2. Create a new policy:

   | Field | Value |
   |---|---|
   | Name | `Zitadel Exchange` |
   | Issuer | `http://localhost:8088` (your `ZITADEL_ISSUER`) |
   | JWKS URI | `http://localhost:8088/oauth/v2/keys` |
   | Subject token type | `urn:ietf:params:oauth:token-type:access_token` |

3. Link this policy to the OAuth application created in 3.1.

### 3.3 Add OBO credentials to the connector config

In Knowledge Mesh admin UI (http://localhost:8080), edit the ServiceNow
connector for the target org.  Add the following to the **Config JSON**:

```json
{
  "instance_url": "https://dev12345.service-now.com",
  "username": "svc_account",
  "password": "existing-service-account-password",
  "obo_client_id": "<Client ID from 3.1>",
  "obo_client_secret": "<Client Secret from 3.1>"
}
```

The `username` / `password` fields continue to be used for background sync
jobs.  The `obo_*` fields are used exclusively for query-time OBO.

---

## Part 4 — Verify the full OBO flow

### 4.1 Get a Zitadel token

```bash
# Exchange username/password for an access token (dev convenience)
curl -X POST http://localhost:8088/oauth/v2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=<your-client-id>" \
  -d "username=<user@example.com>" \
  -d "password=<password>" \
  -d "scope=openid profile email" \
  | jq .access_token
```

### 4.2 Send a chat request with the Zitadel token

```bash
export TOKEN="<access_token from above>"

curl -X POST http://localhost:8000/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I reset my password?"}' \
  --no-buffer
```

Watch the backend logs — you should see:

```
INFO OBO token exchange succeeded for instance https://dev12345.service-now.com
```

If OBO is not yet configured, retrieval falls back to pgvector silently:

```
# No OBO log line = pgvector-only retrieval (expected before SN is configured)
```

---

## How the code fits together

| File | Role |
|---|---|
| `auth/oidc.py` | Validates Zitadel RS256 JWT via JWKS; maps claims → user dict |
| `api/deps.py` | `require_user` tries HS256 first, falls back to OIDC |
| `api/deps.py` | `extract_zitadel_token` returns raw token only for RS256 tokens |
| `connectors/snow_token_exchange.py` | `exchange_for_snow_token` — RFC 8693 exchange; `snow_kb_search` — live SN search |
| `agent/state.py` | `user_zitadel_token` field threads the token through the graph |
| `api/main.py` | Sets `user_zitadel_token` in initial state for both `/chat` endpoints |
| `agent/nodes.py` | `retriever_node` runs OBO search and merges with pgvector results |

---

## Troubleshooting

**OBO exchange returns 400 from ServiceNow**  
→ Check that the Token Exchange policy is linked to the correct OAuth app.  
→ Verify the `Issuer` in the policy matches `ZITADEL_ISSUER` exactly (no trailing slash).

**`oidc_enabled()` returns False**  
→ `ZITADEL_ISSUER` is not set in `.env` or not passed into the backend container.

**JWKS fetch fails on startup**  
→ Zitadel may still be booting.  The JWKS client fetches lazily on first
request, so this resolves once Zitadel is healthy.

**User lands in wrong org**  
→ The `knowledge_mesh_org_id` claim is missing from the token.  Check that
the Zitadel action in Part 2.2 is assigned and the org ID mapping is correct.
