"""
OIDC token validation for Zitadel (and any standard OIDC provider).

Responsibilities
----------------
- Fetch and cache the provider's JWKS (public keys).
- Validate RS256 JWTs issued by Zitadel.
- Return a normalised user dict compatible with the local-auth user dict so
  the rest of the stack (deps.require_user) needs no extra branching.

The JWKS is cached for JWKS_TTL_SECONDS and refreshed lazily on the next
request after expiry.  No background thread — this keeps the module simple.

Docker Compose note
-------------------
Zitadel identifies its instance by matching the incoming HTTP ``Host`` header
against ``ZITADEL_EXTERNALDOMAIN:ZITADEL_EXTERNALPORT`` (i.e. "localhost:8088").
When the backend fetches JWKS via the internal service name ``zitadel:8080``
the Host header becomes ``zitadel:8080``, which Zitadel rejects.

Fix: reach Zitadel on the internal address (``ZITADEL_INTERNAL_URL``) while
spoofing ``Host: localhost:8088`` so the instance lookup succeeds.  The ``iss``
claim in the JWT is still validated against the public issuer URL.
"""
from urllib.parse import urlparse
from typing import Any

import jwt
from jwt import PyJWKClient, PyJWKClientError

from rag_chatbot.config import settings

# ---------------------------------------------------------------------------
# JWKS client — one instance per process, lazily initialised
# ---------------------------------------------------------------------------

_jwks_client: PyJWKClient | None = None
_jwks_client_issuer: str = ""  # tracks which issuer the client was built for


def _jwks_host_header(issuer: str) -> str:
    """Return the Host header value Zitadel expects (domain[:port])."""
    parsed = urlparse(issuer)
    host = parsed.hostname or "localhost"
    port = parsed.port
    # Omit port for standard HTTP/HTTPS ports
    if port and port not in (80, 443):
        return f"{host}:{port}"
    return host


def _get_jwks_client() -> PyJWKClient:
    """Return (or create) a PyJWKClient pointed at the configured Zitadel issuer.

    Uses ``zitadel_internal_url`` (if set) for the TCP connection so the
    backend can reach Zitadel inside Docker, but spoofs the ``Host`` header to
    match the public issuer URL so Zitadel accepts the request.
    """
    global _jwks_client, _jwks_client_issuer

    issuer = settings.zitadel_issuer.rstrip("/")
    # Use the internal Docker service URL for the actual TCP connection.
    fetch_base = (settings.zitadel_internal_url or issuer).rstrip("/")
    jwks_uri = f"{fetch_base}/oauth/v2/keys"

    if _jwks_client is None or _jwks_client_issuer != issuer:
        # Spoof Host so Zitadel's instance-routing accepts the request even
        # when we connect via the internal service name.
        host_header = _jwks_host_header(issuer)
        _jwks_client = PyJWKClient(
            jwks_uri,
            cache_keys=True,
            headers={"Host": host_header},
        )
        _jwks_client_issuer = issuer

    return _jwks_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def oidc_enabled() -> bool:
    """True when a Zitadel issuer is configured."""
    return bool(settings.zitadel_issuer)


async def validate_oidc_token(raw_token: str) -> dict[str, Any]:
    """
    Validate a Zitadel-issued JWT and return a user dict.

    Returns
    -------
    dict with keys: id, email, name, role, org_id, is_active
        - id       : Zitadel subject claim (string used as a stable identifier)
        - email    : from the "email" claim
        - name     : from "name" or "preferred_username"
        - role     : "member" by default; elevated to "admin" via Zitadel roles
        - org_id   : None (org mapping happens via email-domain rules or Zitadel
                     organisation claims — extend _map_org_id() as needed)
        - is_active: always True for valid tokens

    Raises
    ------
    jwt.InvalidTokenError  on any validation failure (expired, wrong issuer, etc.)
    """
    if not oidc_enabled():
        raise jwt.InvalidTokenError("OIDC not configured")

    client = _get_jwks_client()

    try:
        signing_key = client.get_signing_key_from_jwt(raw_token)
    except PyJWKClientError as exc:
        raise jwt.InvalidTokenError(f"JWKS fetch/key lookup failed: {exc}") from exc

    issuer = settings.zitadel_issuer.rstrip("/")

    # Build the accepted audience list.
    #
    # Zitadel PKCE access tokens set `aud` to the *frontend* client ID —
    # the backend client ID only appears when the token is acquired via a
    # service-account or OBO exchange.  Accept both so browser-issued tokens
    # (aud = frontend) and server-issued tokens (aud = backend) both pass.
    accepted: list[str] = []
    if settings.zitadel_frontend_client_id:
        accepted.append(settings.zitadel_frontend_client_id)
    if settings.zitadel_backend_client_id:
        accepted.append(settings.zitadel_backend_client_id)

    decode_options: dict = {"verify_aud": bool(accepted)}
    audience = accepted if accepted else None

    payload = jwt.decode(
        raw_token,
        signing_key.key,
        algorithms=["RS256"],
        options=decode_options,
        issuer=issuer,
        audience=audience,
    )

    return await _claims_to_user(payload)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _claims_to_user(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Zitadel JWT claims → internal user dict."""
    sub = payload.get("sub", "")
    email = payload.get("email", "") or payload.get("preferred_username", "")
    name = payload.get("name") or payload.get("preferred_username") or email

    # Role resolution — priority order:
    # 1. knowledge_mesh_role custom claim (set by Zitadel Action — most authoritative)
    # 2. urn:zitadel:iam:org:project:roles (Zitadel project role assignment)
    # 3. Default: "member"
    role: str = "member"

    action_role = payload.get("knowledge_mesh_role", "")
    if action_role in ("admin", "superadmin", "member"):
        role = action_role
    else:
        zitadel_roles: Any = payload.get("urn:zitadel:iam:org:project:roles", {})
        project_roles: list[str] = []
        if isinstance(zitadel_roles, dict):
            project_roles = list(zitadel_roles.keys())
        elif isinstance(zitadel_roles, list):
            project_roles = zitadel_roles
        if "superadmin" in project_roles:
            role = "superadmin"
        elif "admin" in project_roles:
            role = "admin"

    return {
        "id": sub,           # string, not int — callers that need int should cast
        "email": email,
        "name": name,
        "role": role,
        "org_id": await _map_org_id(payload),
        "is_active": True,
    }


async def _map_org_id(payload: dict[str, Any]) -> int | None:
    """
    Derive the internal org_id from Zitadel claims.

    Priority order:
    1. "knowledge_mesh_org_id" custom claim  (set via Zitadel Action)
    2. Email-domain lookup in org_domains table
    3. None → falls into default org

    The DB lookup is cheap (primary-key scan) and results can be cached
    at the application level if needed.
    """
    # 1. Explicit custom claim wins
    custom = payload.get("knowledge_mesh_org_id")
    if custom is not None:
        try:
            return int(custom)
        except (TypeError, ValueError):
            pass

    # 2. Email-domain → org lookup
    email = payload.get("email", "") or payload.get("preferred_username", "")
    if "@" in email:
        domain = email.rsplit("@", 1)[-1].lower()
        try:
            from rag_chatbot.db.connection import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT org_id FROM org_domains WHERE domain = $1", domain
                )
            if row:
                return int(row["org_id"])
        except Exception:
            pass  # DB unavailable during startup — fall through

    return None
