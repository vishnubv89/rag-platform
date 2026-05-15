# Deploy to DigitalOcean App Platform

## Prerequisites

1. Install `doctl` — [installation guide](https://docs.digitalocean.com/reference/doctl/how-to/install/)
2. Authenticate: `doctl auth init`
3. Connect your GitHub repo to DigitalOcean (once, via the DO dashboard)

## Steps

### 1. Create a Managed Postgres with pgvector

```bash
# Create the cluster (takes ~5 min)
doctl databases create rag-db \
  --engine pg \
  --version 16 \
  --size db-s-1vcpu-1gb \
  --region nyc1

# Note the cluster ID from the output, then enable pgvector:
doctl databases db create <CLUSTER_ID> rag_db
# Connect and run: CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Set secrets

In the DO dashboard → Apps → (your app) → Settings → App-Level Environment Variables, add:

| Key | Value |
|-----|-------|
| `GOOGLE_API_KEY` | Your Gemini API key |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `ADMIN_SECRET_KEY` | `openssl rand -hex 24` |

### 3. Edit app.yaml

Replace `YOUR_GITHUB_ORG/rag-platform` with your actual GitHub repo path in `deploy/do/app.yaml`.

### 4. Deploy

```bash
# First deploy
doctl apps create --spec deploy/do/app.yaml

# Subsequent updates
doctl apps update <APP_ID> --spec deploy/do/app.yaml

# Watch deploy logs
doctl apps logs <APP_ID> --follow
```

### 5. Bind the database

In the DO dashboard → Apps → your app → Settings → rag-backend → Databases → Attach Database → select `rag-db`. This injects `DATABASE_URL` automatically.

### 6. Run migrations (first time only)

```bash
# Get a connection string from the DO dashboard, then:
psql "$DATABASE_URL" -f backend/src/rag_chatbot/db/migrations/001_multitenancy.sql
# ... repeat for 002 through 006
```

Subsequent deploys run migrations automatically via the `migrate` pre-deploy job.

## Estimated cost

| Component | Size | $/month |
|-----------|------|---------|
| rag-backend | apps-s-1vcpu-0.5gb | ~$12 |
| rag-frontend | apps-s-1vcpu-0.5gb | ~$12 |
| rag-admin-ui | apps-s-1vcpu-0.5gb | ~$12 |
| Postgres (managed) | db-s-1vcpu-1gb | ~$15 |
| **Total** | | **~$51/mo** |
