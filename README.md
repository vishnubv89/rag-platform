# RAG Platform

A production-grade, multi-tenant AI chatbot backed by **Agentic Retrieval-Augmented Generation (RAG)**. Unlike naive RAG systems that retrieve once and answer, this platform uses a **LangGraph agent loop** that reasons, evaluates chunk quality, rewrites queries on failure, and only generates an answer when it is confident the context is relevant — and **asks for clarification instead of hallucinating** when it isn't.

Built as a **3-pod monorepo** — independently deployable via Docker Compose or Kubernetes Helm charts.

---

## Architecture

```
                         Internet / Ingress
              ┌───────────────┬───────────────┐
              ▼               ▼               ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │  FRONTEND    │ │   BACKEND    │ │   ADMIN-UI   │
     │  React+Vite  │ │   FastAPI    │ │  FastAPI     │
     │  Tailwind    │ │  LangGraph   │ │  +Jinja2     │
     │  Zustand     │ │  FastMCP     │ │  Bootstrap 5 │
     │  nginx       │ │  Gemini LLM  │ │              │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │  fetch()       │         httpx  │
            └────────────────►◄────────────────┘
                             │
                             ▼
                  ┌────────────────────┐
                  │  PostgreSQL        │
                  │  + pgvector        │
                  │  HNSW + GIN index  │
                  └────────────────────┘
```

| Pod | Default URL | Role |
|---|---|---|
| **frontend** | `http://localhost:5173` | Chat UI — send messages, upload files, browse history |
| **backend** | `http://localhost:8000` | Core RAG engine — agent loop, embeddings, hybrid search, admin API |
| **admin-ui** | `http://localhost:8080` | Admin panel — orgs, docs, settings, analytics |

> **Deep-dive:** See [PRODUCT.md](./PRODUCT.md) for full architecture diagrams, API reference, database schema, and deployment playbooks.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM + Embeddings | `google-genai` — `gemini-2.0-flash` / `text-embedding-004` | Unified SDK, 768d Matryoshka embeddings, task-type aware |
| Agent loop | LangGraph `StateGraph` | Conditional edges, loop control, clarify fallback instead of hallucination |
| Knowledge grounding | Conservative grader + `clarify_node` | Refuses to use general knowledge; asks clarifying questions when KB has no answer |
| Follow-up suggestions | `POST /chat/followup` async after response | 3 contextual chips per reply, always via Gemini regardless of org's LLM |
| Connector sync | ServiceNow, SharePoint, Confluence, Google Drive, Zendesk, Jira | Automated knowledge base ingestion from enterprise systems |
| Tool interface | FastMCP | Model Context Protocol — standard LLM tool interface |
| Vector search | pgvector HNSW (`m=16`, `ef_construction=64`, cosine) | In-Postgres vectors, no separate vector DB to operate |
| Full-text search | PostgreSQL `tsvector` + GIN index | Native BM25 with no extra deps |
| Hybrid fusion | Reciprocal Rank Fusion (RRF) SQL | Combines semantic + keyword rankings without tuning weights |
| Database driver | asyncpg | 10-20× faster than psycopg2 for async workloads |
| Backend API | FastAPI + Pydantic v2 | Auto schema, async-native |
| Frontend | React 19 + Vite + TypeScript | Fast builds, strict types |
| State management | Zustand with localStorage persist | Simple, no boilerplate, sessions survive refresh |
| Styling | Tailwind CSS v4 (Vite plugin) | No config file, no purge step |
| Admin UI | Jinja2 + Bootstrap 5 CDN + Chart.js | Zero frontend build step |
| Admin auth | Starlette SessionMiddleware + backend user DB | Role-gated login (superadmin/admin only), 8h signed cookie session |
| Chunking | tiktoken `cl100k_base`, 300 tokens / 50 overlap | Deterministic, model-aligned token boundaries |
| Orchestration | Helm (3 charts) + Docker Compose | Same config for local dev and Kubernetes |

---

## Quick Start

### Prerequisites

- Docker + Docker Compose v2
- A [Gemini API key](https://aistudio.google.com/app/apikey)

### Run locally

```bash
git clone https://github.com/vishnubv89/rag-platform.git
cd rag-platform

cp .env.example .env
# Edit .env — set GEMINI_API_KEY and ADMIN_SECRET_KEY

docker compose up --build
```

| Service | URL |
|---|---|
| Chat UI | http://localhost:5173 |
| Backend API docs | http://localhost:8000/docs |
| Admin panel | http://localhost:8080 |

### Verify it works

```bash
# Backend health
curl http://localhost:8000/health

# List orgs (uses your ADMIN_SECRET_KEY)
curl -H "X-Admin-Key: change-me" http://localhost:8000/admin/orgs

# Ingest a document
curl -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","text":"pgvector enables semantic search in PostgreSQL."}'

# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What does pgvector do?","history":[]}'
```

---

## Kubernetes / Helm Deployment

```bash
# Backend
helm upgrade --install rag-backend ./helm/backend \
  --set secrets.GEMINI_API_KEY=$GEMINI_API_KEY \
  --set secrets.DATABASE_URL=$DATABASE_URL \
  --set secrets.ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY \
  --set ingress.host=api.rag.example.com

# Frontend
helm upgrade --install rag-frontend ./helm/frontend \
  --set env.VITE_API_BASE_URL=https://api.rag.example.com \
  --set ingress.host=chat.rag.example.com

# Admin UI (restricted to internal CIDR)
helm upgrade --install rag-admin ./helm/admin-ui \
  --set secrets.ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY \
  --set env.BACKEND_URL=http://rag-backend:8000 \
  --set ingress.host=admin.rag.example.com \
  --set ingress.whitelistSourceRange="10.0.0.0/8"
```

The backend chart includes an **HPA** (min 2, max 6 replicas at 70% CPU). Admin-UI communicates with the backend over internal K8s DNS — `X-Admin-Key` never crosses a public network boundary.

---

## Project Structure

```
rag-platform/
├── docker-compose.yml
├── PRODUCT.md                    # Full technical reference
│
├── backend/                      # FastAPI + LangGraph + FastMCP
│   ├── Dockerfile
│   └── src/rag_chatbot/
│       ├── agent/                # graph.py, nodes.py, state.py
│       ├── api/                  # main.py, admin_router.py, deps.py
│       ├── db/                   # schema.sql, migrations/
│       ├── embeddings/           # gemini_embedder.py
│       ├── ingestion/            # pipeline.py, chunker.py, loader.py
│       ├── mcp_server/           # server.py (hybrid_search, ingest, rerank)
│       └── retrieval/            # vector_store.py (RRF hybrid search)
│
├── frontend/                     # React + Vite + TypeScript
│   ├── Dockerfile                # multi-stage: node builder → nginx
│   └── src/
│       ├── api/client.ts
│       ├── store/chatStore.ts    # Zustand + localStorage
│       ├── hooks/useChat.ts
│       └── components/           # ChatWindow, MessageBubble, FileUpload, …
│
├── admin-ui/                     # FastAPI + Jinja2
│   ├── Dockerfile
│   └── src/admin_ui/
│       ├── client.py             # httpx → backend (auto-injects X-Admin-Key)
│       ├── routers/              # dashboard, documents, settings, orgs, analytics
│       └── templates/            # Bootstrap 5 HTML templates
│
└── helm/
    ├── backend/                  # Deployment, Service, Ingress, HPA, Secret
    ├── frontend/                 # Deployment, Service, Ingress
    └── admin-ui/                 # Deployment, Service, Ingress, Secret, ConfigMap
```

---

## Configuration

### Backend environment variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | **required** | Google AI Studio API key |
| `DATABASE_URL` | `postgresql://rag:rag_secret@localhost/rag_db` | asyncpg connection string |
| `ADMIN_SECRET_KEY` | `change-me` | Bootstrap admin key (change before production) |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:8080"]` | Allowed frontend origins |
| `APP_ENV` | `development` | `development` or `production` |

### Per-org runtime config (via admin panel)

| Key | Default | Description |
|---|---|---|
| `llm_model` | `gemini-2.0-flash` | LLM model name |
| `embedding_model` | `text-embedding-004` | Embedding model |
| `chunk_size` | `300` | Tokens per chunk |
| `chunk_overlap` | `50` | Overlap tokens between chunks |
| `retrieval_top_k` | `8` | Chunks returned per search |
| `grader_max_loops` | `3` | Max retrieval-rewrite cycles |
| `reranker_top_k` | `5` | Chunks after reranking |

---

## What's New in v0.2

| Area | Change |
|---|---|
| **Knowledge grounding** | Grader is now conservative — excludes chunks on any doubt. Generator is context-only and cannot use general knowledge. When all retry loops exhaust without relevant chunks, a new `clarify_node` asks the user for clarification instead of hallucinating. |
| **Follow-up suggestions** | After every assistant response, three contextual follow-up chips are generated asynchronously via `POST /chat/followup`. Always uses Gemini regardless of the org's primary LLM setting. |
| **Admin authentication** | Admin-ui now has a login page backed by the backend user database. Only `superadmin` and `admin` roles are admitted. Sessions stored in a signed httponly cookie with 8-hour TTL. |
| **Persistent org scope** | Org selection in the admin panel is now stored in a cookie (`admin_org_scope`) rather than a URL parameter — survives navigations, redirects, and form submissions without leaking into every link. |
| **New connectors** | Google Drive, Zendesk, and Jira connectors added alongside existing ServiceNow, SharePoint, and Confluence. |
| **Embedding bug fix** | Fixed a Google GenAI SDK quirk: `embed_content(contents=list)` always returns exactly 1 embedding regardless of list length. Fixed by calling once per text. |
| **Conversational tone** | Generator no longer mentions "based on the provided document chunks" — answers feel person-to-person. |

---

## Roadmap & Scaling

### Near-term improvements

| Area | Improvement |
|---|---|
| **Streaming** | Add `StreamingResponse` to `/chat`; switch frontend to `EventSource` for token-by-token display |
| **Auth** | Replace static `X-Admin-Key` with JWT/OIDC for the frontend; add per-user session auth |
| **Reranker** | Swap the Gemini-based grader for a dedicated cross-encoder reranker (Cohere Rerank, `bge-reranker-v2`) for faster, cheaper relevance scoring |
| **File types** | Add DOCX, HTML, and web URL ingestion alongside PDF/TXT/MD |
| **Chunk strategy** | Add semantic chunking (split on paragraph/heading boundaries rather than fixed token count) |
| **Observability** | Emit OpenTelemetry spans for each LangGraph node; export to Jaeger or Grafana Tempo |
| **Tests** | Unit tests for nodes; integration tests against a real PG container (use `pytest-asyncio` + `testcontainers`) |

### Scaling the backend

| Bottleneck | Solution |
|---|---|
| **Gemini API rate limits** | Batch embed requests; add exponential backoff; consider multiple API keys per org |
| **LangGraph CPU per request** | The agent loop is stateless — scale backend horizontally via the existing HPA (already min 2, max 6) |
| **Embedding throughput** | Queue ingestion jobs (Celery + Redis or pgqueuer) so large uploads don't block the request thread |
| **Database read contention** | Add a read replica; route hybrid search queries to the replica |
| **pgvector at large scale** | Tune HNSW `ef_search` dynamically per query; partition the `chunks` table by `org_id` for multi-tenant isolation at the storage level |
| **Cold start latency** | Pre-warm asyncpg connection pools on pod startup; set `min_size=2` in the pool config |

### Scaling the frontend

| Area | Solution |
|---|---|
| **Session storage** | Move sessions from localStorage to a backend-persisted table (already have `chat_logs`) — enables cross-device history |
| **Real-time updates** | Add WebSocket or SSE for collaborative sessions or admin push notifications |
| **Bundle size** | Lazy-load `HistoryPanel` and `OrgSelector`; code-split by route if pages are added |
| **CDN delivery** | Serve the nginx static bundle from a CDN edge (CloudFront, Cloudflare Pages) — zero backend load for the shell |

### Multi-tenancy at scale

| Area | Solution |
|---|---|
| **Org isolation** | Move from `org_id` column filtering to **Row Level Security (RLS)** in PostgreSQL — prevents cross-tenant data leaks at the DB level |
| **Per-org rate limiting** | Add a Redis-backed rate limiter middleware keyed on `org_id` |
| **Per-org model routing** | Extend `app_config` to support alternative LLM providers per org (OpenAI, Anthropic) via a provider abstraction layer |
| **Billing** | Aggregate `prompt_tokens + completion_tokens` from `chat_logs` for usage-based billing; expose a `/admin/analytics/billing` endpoint |

### Infrastructure evolution

```
Current (v0.1)          →  Near-term (v0.2)           →  Scale-out (v1.0)
─────────────────────      ─────────────────────────      ──────────────────────
3 pods + PostgreSQL        + Redis (cache + queues)        Separate read replica
Single-region              + Celery workers                PgBouncer connection pool
HPA on backend             + OpenTelemetry tracing         Multi-region ingress
Static admin key           + JWT / OIDC auth               RLS on all tables
Batch embedding            + Streaming chat                Async embedding pipeline
                           + Cross-encoder reranker        Per-org LLM routing
```

---

## Contributing

1. Fork the repo and create a feature branch
2. Run `docker compose up` to spin up the full stack locally
3. Backend: `cd backend && pip install -e ".[dev]" && pytest`
4. Frontend: `cd frontend && npm install && npm run build`
5. Open a PR — describe what changed and why

---

## License

MIT
