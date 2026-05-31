# Knowledge Mesh — Developer Guide

## What This Is
3-service Agentic RAG platform: a FastAPI backend, a React frontend (chat UI + Doc Curator), and a React admin UI. Backed by PostgreSQL + pgvector, MinIO, and optionally Langfuse + Zitadel.

## Monorepo Layout
```
rag-platform/
├── backend/                     # FastAPI + LangGraph service
│   └── src/rag_chatbot/
│       ├── api/
│       │   ├── main.py          # App factory (~80 lines)
│       │   ├── schemas.py       # All Pydantic request/response models
│       │   └── routers/         # One file per domain
│       │       ├── chat.py      # /chat, /chat/stream, /chat/followup, /chat/{id}/feedback
│       │       ├── sessions.py  # /chat/sessions CRUD
│       │       ├── curate.py    # /curate, /curate/categories, /curate/sync
│       │       └── suggest.py   # /suggest, /docs/{id}/topics
│       ├── agent/               # LangGraph nodes and graph definition
│       ├── auth/                # JWT middleware and user resolution
│       ├── connectors/          # ServiceNow, MinIO, future connectors
│       ├── db/
│       │   ├── connection.py    # asyncpg pool factory
│       │   └── repositories/    # All SQL queries (no inline SQL in routes)
│       │       ├── chat.py
│       │       ├── docs.py
│       │       └── orgs.py
│       ├── embeddings/          # Embedding model wrappers
│       ├── ingestion/           # Document chunking and ingestion pipeline
│       ├── llm/                 # LLM client (Gemini, Anthropic, NVIDIA NIM)
│       └── retrieval/           # Hybrid search (BM25 + pgvector RRF)
├── frontend/                    # Chat UI + Doc Curator (React + Vite)
│   └── src/
│       ├── api/client.ts        # Typed API client
│       ├── components/          # UI components
│       ├── hooks/               # Data-fetching hooks
│       ├── store/               # Zustand state stores
│       └── types/index.ts       # TypeScript interfaces (source of truth)
├── admin-ui/                    # Admin dashboard (React + Vite)
├── .github/workflows/ci.yml     # Lint + test on every push/PR
├── .env.example                 # Required environment variables template
└── docker-compose.yml           # Full local stack
```

## Running Locally

### Prerequisites
- Docker Desktop
- Copy `.env.example` → `.env` and fill in values

### Start everything
```bash
docker compose up -d
```

| Service | URL |
|---------|-----|
| Chat UI | http://localhost:8080 |
| API docs | http://localhost:8000/docs |
| Admin UI | http://localhost:8081 |
| Langfuse | http://localhost:3000 |
| MinIO console | http://localhost:9001 |

## Development Workflow

```bash
# 1. Branch from main
git checkout main && git pull
git checkout -b feat/your-feature   # or fix/ perf/ chore/

# 2. Make changes, then lint
cd backend && ruff check src/ --fix && ruff format src/

# 3. Run tests
pytest tests/ -v

# 4. Rebuild and verify
docker compose build backend frontend
docker compose up -d

# 5. Push and open PR against main
git push -u origin feat/your-feature
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Split-format LLM response (`METADATA` / `---CONTENT---`) | Document body never enters a JSON string → no escaping issues with quotes or newlines |
| RRF score fast-path in retrieval | Skip LLM grading when top chunk score ≥ 0.016 — cuts latency from 40s to <6s |
| Repository layer for DB | All SQL in `db/repositories/` — route handlers never write SQL inline |
| KCS v6 + ITIL 4 for curation | Industry-standard knowledge article quality dimensions (Structure, Clarity, Completeness, Accuracy, Actionability, Findability, Readability) |
| 0–100 score scale with +10 minimum | Explicit scale prevents LLM from using 0–1 boolean; server-side floor guarantees visible improvement |

## Environment Variables
See `.env.example` for full list with descriptions.

## CI
GitHub Actions runs on every push to `main` and all feature branches:
- `ruff check` + `ruff format --check` (backend)
- `mypy --ignore-missing-imports` (backend)
- `pytest` (backend)
- `tsc --noEmit` (frontend)
