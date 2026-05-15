# RAG Platform

A production-grade, multi-tenant AI chatbot backed by **Agentic Retrieval-Augmented Generation (RAG)**. Unlike naive RAG systems that retrieve once and answer, this platform uses a **LangGraph agent loop** that understands conversation history, retrieves relevant context, evaluates chunk quality, rewrites queries on failure, and only generates an answer when confident — **asking for clarification instead of hallucinating** when it isn't.

Built as a **3-pod monorepo** — independently deployable via Docker Compose or Kubernetes Helm charts.

---

## Architecture

```
                              Internet / Ingress
               ┌───────────────┬───────────────┬───────────────┐
               ▼               ▼               ▼               ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │  FRONTEND    │ │   BACKEND    │ │   ADMIN-UI   │ │   ZITADEL    │
      │  React+Vite  │ │   FastAPI    │ │  FastAPI     │ │  OIDC IdP    │
      │  Tailwind    │ │  LangGraph   │ │  +Jinja2     │ │  SSO + OBO   │
      │  Zustand     │ │  Multi-LLM   │ │  Bootstrap 5 │ └──────────────┘
      │  nginx       │ │  FastMCP     │ │              │
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             │  fetch/SSE     │         httpx  │
             └────────────────►◄────────────────┘
                              │
               ┌──────────────┴───────────────┐
               ▼                              ▼
  ┌────────────────────────┐    ┌─────────────────────────┐
  │   PostgreSQL + pgvector │    │   Langfuse v3            │
  │   HNSW + GIN indexes    │    │   ClickHouse + Redis     │
  │   users, orgs, chunks  │    │   MinIO + worker          │
  └────────────────────────┘    └─────────────────────────┘
```

| Pod | Default URL | Role |
|---|---|---|
| **frontend** | `http://localhost:5173` | Chat UI — streaming responses, file upload, history, feedback |
| **backend** | `http://localhost:8000` | Core RAG engine — agent loop, multi-LLM, hybrid search, auth |
| **admin-ui** | `http://localhost:8080` | Admin panel — orgs, docs, settings, analytics, connectors |
| **langfuse** | `http://localhost:3000` | Observability — traces, generations, retrieval spans |
| **zitadel** | `http://localhost:8088` | SSO Identity Provider |

> **Deep-dive:** See [PRODUCT.md](./PRODUCT.md) for full architecture diagrams, agent pipeline, API reference, database schema, SSO setup, and deployment playbooks.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **LLM** | Pluggable: Gemini 2.0 Flash · Claude 3.5 Sonnet · NVIDIA NIM / Ollama | One abstraction layer; switch per-org via admin panel without restart |
| **Embeddings** | `text-embedding-004` (768d, always Gemini) | Matryoshka: <2% recall drop vs 3072d; halves storage |
| **Agent loop** | LangGraph `StateGraph` | Conditional edges, retry loops, `astream_events` for streaming |
| **Conversational context** | `contextualize_node` — rewrites follow-ups with 3-turn history | *"tell me more about that"* resolves to a self-contained query before retrieval |
| **Knowledge grounding** | Conservative grader + `clarify_node` | Refuses general knowledge fill-in; asks a clarifying question when KB has no answer |
| **Streaming** | `POST /chat/stream` → LangGraph `astream_events` → SSE | Tokens rendered in real time; sources appear on completion |
| **KB overview intent** | `kb_overview_node` — summarises all document titles | Bypasses retrieval for "what's in the knowledge base?" questions |
| **Hybrid search** | pgvector HNSW + PostgreSQL `tsvector` fused via RRF | Semantic + keyword, no external search service |
| **SSO** | Zitadel OIDC — PKCE frontend, JWKS backend validation | Enterprise login, org claims, role-based access |
| **OBO token exchange** | Zitadel → ServiceNow per-user token | Live KB search respects ServiceNow article ACLs |
| **Observability** | Langfuse v3 (ClickHouse + Redis + MinIO) + SDK v4 | Full trace tree: chain → retriever → generation, with user/session/org tags |
| **User feedback** | Thumbs up/down stored in `chat_logs.feedback` | Collected via `POST /chat/feedback/{log_id}` |
| **Connector sync** | ServiceNow, SharePoint, Confluence, Google Drive, Zendesk, Jira | APScheduler-based automated KB ingestion |
| **Tool interface** | FastMCP | MCP-standard — works with Claude Desktop and other agents |
| **Rate limiting** | slowapi 20 req/min per IP | Protects chat and ingest endpoints |
| **Database driver** | asyncpg | 10-20× faster than psycopg2 for async workloads |
| **Backend API** | FastAPI + Pydantic v2 | Auto-schema, async-native |
| **Frontend** | React 19 + Vite + TypeScript | Fast builds, strict types, SSE-native |
| **State** | Zustand with `persist` + Date-safe serialization | Sessions survive refresh; no white-screen crash on history load |
| **Styling** | Tailwind CSS v4 (Vite plugin) | No config file, no purge step |
| **Admin UI** | Jinja2 + Bootstrap 5 CDN + Chart.js | Zero frontend build step |
| **Admin auth** | Starlette `SessionMiddleware` + backend user DB | Role-gated login (superadmin/admin only), 8h signed cookie |
| **Chunking** | tiktoken `cl100k_base`, 300 tokens / 50 overlap | Deterministic, model-aligned boundaries |
| **Orchestration** | Helm (3 charts) + Docker Compose (13 services) | Same config — local dev to Kubernetes |

---

## Quick Start

### Prerequisites

- Docker + Docker Compose v2
- A [Gemini API key](https://aistudio.google.com/app/apikey)

### Run locally

```bash
git clone https://github.com/your-org/rag-platform.git
cd rag-platform

cp .env.example .env
# Edit .env:
#   GEMINI_API_KEY=your-key
#   ADMIN_SECRET_KEY=your-secret

docker compose up --build
```

First build: ~4 minutes (downloads images, installs deps). Subsequent starts: ~30 seconds.

### Access the services

| Service | URL |
|---|---|---|
| Chat UI | http://localhost:5173 |
| Admin panel | http://localhost:8080 |
| Backend Swagger | http://localhost:8000/docs | 
| Langfuse traces | http://localhost:3000 |

### Verify it works

```bash
# Backend health
curl http://localhost:8000/health

# List orgs
curl -H "X-Admin-Key: your-secret" http://localhost:8000/admin/orgs

# Ingest a document
curl -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"title":"Password Policy","text":"To reset your password, visit the self-service portal and click Forgot Password."}'

# Chat (blocking)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"message":"How do I reset my password?","history":[]}'
```

---

## Agentic RAG Pipeline

Every chat message flows through an 8-node LangGraph graph:

```
START
  └─► contextualize   — resolves follow-up references using last 3 turns
        └─► intent    — regex: chitchat? KB overview? or retrieve?
              ├─ chitchat ──────────────────────────────────► generator ──► END
              ├─ kb_overview ──────────────────────────────► kb_overview ──► END
              └─ retrieve ──► retriever (hybrid: BM25 + cosine RRF)
                                └─► grader (single batched LLM call)
                                      ├─ relevant ─────────► generator ──► END
                                      └─ irrelevant
                                            ├─ loops left ── rewriter ──► retriever (retry)
                                            └─ exhausted ─── clarify ──► END
```

| Node | What it does |
|---|---|
| `contextualize` | Rewrites *"tell me more about that"* → *"What are the steps for resetting a ServiceNow password?"* using conversation history. No-op on first turn. |
| `intent` | Keyword regex — routes chitchat, KB-overview questions, and retrieval queries without an LLM call |
| `kb_overview` | Fetches all doc titles for the org; LLM summarises into a grouped topic overview |
| `retriever` | RRF hybrid search (BM25 + pgvector cosine); OBO live ServiceNow search if user has a Zitadel token |
| `grader` | Single batched LLM call grades all chunks at once; conservative — excludes any chunk that doesn't directly answer the query |
| `rewriter` | Reformulates the query with different keywords for the next retrieval attempt |
| `generator` | Injects conversation history + context chunks; streams tokens via SSE; strictly grounded — no general knowledge fill-in |
| `clarify` | Fires when grading exhausts all loops; asks a clarifying question instead of hallucinating |

---

## Conversational Context

Follow-up questions now just work:

| What the user types | What the retriever sees |
|---|---|
| *"tell me more about that"* (after password reset) | *"What are the detailed steps for resetting a ServiceNow password?"* |
| *"what does step 2 say?"* | *"What is step 2 in the ServiceNow account unlock procedure?"* |
| *"How often does it sync?"* (after SharePoint connector) | *"How often does the SharePoint connector sync documents?"* |
| *"Reset password"* (first turn — standalone) | *"Reset password"* (unchanged) |

The `generator_node` also injects the prior conversation as context so answers naturally reference previous turns.

---

## Multi-LLM Support

Switch LLM providers per-org via the admin settings panel — no restart needed:

| Provider | `LLM_PROVIDER` | Example models |
|---|---|---|
| Google Gemini (default) | `gemini` | `gemini-2.0-flash`, `gemini-1.5-pro` |
| Anthropic Claude | `anthropic` | `claude-3-5-sonnet-20241022`, `claude-3-haiku-20240307` |
| NVIDIA NIM / OpenAI-compat | `nvidia` | Any model — also works for Groq, Ollama, Together AI |

Embeddings always use Gemini `text-embedding-004` regardless of the chat LLM.

---

## Streaming Chat

`POST /chat/stream` returns an SSE stream:

```
data: {"type": "token", "token": "To "}
data: {"type": "token", "token": "reset "}
data: {"type": "token", "token": "your "}
...
data: {"type": "done", "sources": [...], "loop_count": 1, "session_id": "...", "log_id": 42}
```

The frontend renders tokens in real time. Sources and the feedback buttons appear after the `done` event.

---

## Observability (Langfuse v3)

Every request generates a full trace tree:

```
rag-chat [chain]                user=alice  session=abc  org=acme
  └── retrieval.hybrid_search [retriever]   5 results, titles=[…]
  └── llm.generate [generation]             model=gemini-2.0-flash  in=312 out=89
```

Access the Langfuse UI at **http://localhost:3000** (`admin@rag.local` / `Admin1234!`).

Tracing uses Langfuse v4 SDK with OTEL-based `start_as_current_observation` and `_propagate_attributes` for user/session/org attribution. Disable tracing entirely by setting `LANGFUSE_SECRET_KEY=` (empty string).

---

## SSO & OBO

**Zitadel** handles enterprise SSO:
- PKCE flow in the browser (no client secret exposed)
- JWT validated via JWKS on every backend request
- Org membership and role (`superadmin`, `admin`, `user`) injected into token via Zitadel Action hook

**On-Behalf-Of (OBO)** for ServiceNow:
- When a user with a Zitadel token asks a question, the retriever exchanges their token for a ServiceNow API token scoped to their permissions
- Live ServiceNow KB search runs alongside pgvector — users only see articles their ServiceNow ACLs allow
- Results are merged and deduplicated with pgvector results by `external_id`

---

## Kubernetes / Helm Deployment

```bash
# Backend
helm upgrade --install rag-backend ./helm/backend \
  --set secrets.GEMINI_API_KEY=$GEMINI_API_KEY \
  --set secrets.DATABASE_URL=$DATABASE_URL \
  --set secrets.ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY \
  --set secrets.JWT_SECRET=$JWT_SECRET \
  --set ingress.host=api.rag.example.com

# Frontend
helm upgrade --install rag-frontend ./helm/frontend \
  --set ingress.host=chat.rag.example.com

# Admin UI (internal CIDR only)
helm upgrade --install rag-admin ./helm/admin-ui \
  --set secrets.ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY \
  --set env.BACKEND_URL=http://rag-backend:8000 \
  --set ingress.host=admin.rag.example.com \
  --set ingress.whitelistSourceRange="10.0.0.0/8"
```

The backend chart includes an **HPA** (min 2, max 6 replicas at 70% CPU). Admin-UI communicates with the backend over internal K8s DNS — the admin key never crosses a public network boundary.

---

## Project Structure

```
rag-platform/
├── docker-compose.yml            13 services: backend, frontend, admin-ui,
│                                 postgres, zitadel, langfuse, langfuse-worker,
│                                 clickhouse, redis, minio, minio-init
├── clickhouse/config.xml         ClickHouse Keeper + cluster config
├── PRODUCT.md                    Full technical reference
│
├── backend/
│   └── src/rag_chatbot/
│       ├── observability.py      Langfuse v4 singleton
│       ├── llm/client.py         Multi-LLM: Gemini / Anthropic / NVIDIA NIM
│       ├── agent/
│       │   ├── nodes.py          8 nodes incl. contextualize + kb_overview
│       │   ├── graph.py          LangGraph StateGraph
│       │   └── state.py          AgentState (14 fields)
│       ├── api/
│       │   ├── main.py           /chat, /chat/stream, /chat/feedback
│       │   ├── admin_router.py   Admin REST API
│       │   └── deps.py           JWT + API key auth
│       ├── auth/router.py        /auth/login, /auth/me
│       ├── connectors/           ServiceNow OBO + 5 other connectors
│       ├── retrieval/            Hybrid search (RRF)
│       └── db/                   Schema + migrations
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── MessageBubble.tsx  Date-safe timestamps + feedback buttons
│       │   └── SourceCitations.tsx
│       ├── api/client.ts          sendChatStream(), submitFeedback()
│       └── store/chatStore.ts     Zustand + localStorage
│
├── admin-ui/
│   └── src/admin_ui/
│       ├── routers/connectors.py  Connector status page
│       └── templates/             Bootstrap 5 + Chart.js
│
└── helm/
    ├── backend/     Deployment + HPA (2-6 replicas) + Secret
    ├── frontend/    Deployment + Ingress
    └── admin-ui/    Deployment + IP-restricted Ingress
```

---

## Configuration

### Backend environment variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | **required** | Google AI Studio API key |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `DATABASE_URL` | `postgresql://rag:rag_secret@localhost/rag_db` | asyncpg connection string |
| `LLM_PROVIDER` | `gemini` | `gemini` / `anthropic` / `nvidia` |
| `ADMIN_SECRET_KEY` | `change-me` | Bootstrap admin key |
| `JWT_SECRET` | `change-me-jwt-secret` | Signs platform JWTs |
| `LANGFUSE_SECRET_KEY` | — | Empty string = disable tracing |
| `LANGFUSE_HOST` | `http://langfuse:3000` | Langfuse server URL |
| `ZITADEL_ISSUER` | — | Zitadel OIDC issuer (optional, enables SSO) |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:8080"]` | Allowed frontend origins |

### Per-org runtime config (via admin panel)

| Key | Default | Description |
|---|---|---|
| `llm_provider` | `gemini` | Override LLM provider for this org |
| `llm_model` | `gemini-2.0-flash` | Gemini model |
| `anthropic_model` | `claude-3-5-sonnet-20241022` | Anthropic model |
| `anthropic_api_key` | — | Org-specific Anthropic key |
| `nvidia_model` | — | NVIDIA NIM model |
| `nvidia_base_url` | — | NIM / OpenAI-compat endpoint |
| `chunk_size` | `300` | Tokens per chunk |
| `chunk_overlap` | `50` | Overlap tokens between chunks |
| `retrieval_top_k` | `8` | Chunks returned per search |
| `grader_max_loops` | `3` | Max retrieval-rewrite cycles |

---

## What's New in v0.3

| Area | Change |
|---|---|
| **Conversational context** | New `contextualize_node` as graph entry point — rewrites follow-up questions into standalone queries using the last 3 conversation exchanges; `generator_node` also injects history into the prompt |
| **Langfuse v3 upgrade** | Full infrastructure upgrade: ClickHouse (trace storage), Redis (BullMQ), MinIO (event S3), `langfuse-worker`; ClickHouse Keeper config for single-node cluster |
| **Langfuse SDK v4** | Complete SDK rewrite — `start_as_current_observation(as_type=...)`, `_propagate_attributes` for user/session/org OTEL baggage; removed deprecated `langfuse.callback` and `langfuse.decorators` |
| **Multi-LLM support** | Unified `llm/client.py` with Gemini, Anthropic, and NVIDIA NIM / OpenAI-compatible provider; per-org override via admin settings; client caching per API key |
| **Streaming** | `POST /chat/stream` via LangGraph `astream_events` + SSE; frontend renders tokens in real time; `done` event delivers sources + log_id |
| **User feedback** | Thumbs up/down on every assistant message; `POST /chat/feedback/{log_id}`; stored in `chat_logs.feedback`; `MessageBubble` renders buttons with optimistic update |
| **SSO (Zitadel)** | Full OIDC SSO: PKCE frontend client, JWKS backend validation, Zitadel Action for org/role claim enrichment |
| **OBO for ServiceNow** | Per-user OBO token exchange: Zitadel JWT → ServiceNow API token; live ACL-aware KB search merged with pgvector results |
| **KB overview intent** | `kb_overview_node` — summarises all document titles into a grouped overview when user asks "what's in the knowledge base?"; bypasses retrieval |
| **Admin SSO role management** | Org detail page in admin-ui shows SSO role assignments; Zitadel Action webhook integration |
| **MessageBubble Date fix** | `new Date(message.timestamp)` prevents white-screen crash when Zustand `persist` deserialises timestamps from localStorage as strings |
| **Rate limiting** | `slowapi` 20 req/min per IP on all `/chat` and `/ingest` endpoints |

## What's New in v0.2

| Area | Change |
|---|---|
| **Knowledge grounding** | Conservative grader; `clarify_node` asks for clarification instead of hallucinating when KB has no answer |
| **Follow-up suggestions** | Three contextual follow-up chips via `POST /chat/followup` |
| **Admin authentication** | Login page backed by backend user DB; `superadmin` / `admin` roles; 8h signed cookie |
| **Persistent org scope** | `admin_org_scope` cookie — survives navigations without URL parameter leaking |
| **New connectors** | Google Drive, Zendesk, Jira added |
| **Embedding fix** | Fixed Google GenAI SDK quirk where batch embed always returned 1 result |
| **Conversational tone** | Generator no longer mentions "based on the provided document chunks" |

---

## Roadmap

| Near-term | Description |
|---|---|
| **Cross-device history** | Move sessions from localStorage to backend `chat_logs` table |
| **Cross-encoder reranker** | Swap Gemini grader for Cohere Rerank or `bge-reranker-v2` for faster, cheaper scoring |
| **File types** | DOCX, HTML, web URL ingestion |
| **Semantic chunking** | Split on paragraph / heading boundaries instead of fixed token count |
| **Tests** | `pytest-asyncio` unit + integration tests for all nodes |
| **Row Level Security** | PostgreSQL RLS for true org-level data isolation |
| **Per-org rate limiting** | Redis-backed rate limiter keyed on `org_id` |

---

## Contributing

1. Fork and create a feature branch (`feat/`, `fix/`, `perf/`, `chore/`)
2. `docker compose up` to spin up the full stack
3. Backend: `cd backend && pip install -e ".[dev]" && pytest`
4. Frontend: `cd frontend && npm install && npm run build`
5. Open a PR against `main` — describe what changed and why

---

## License

MIT
