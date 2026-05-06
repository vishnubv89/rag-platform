# RAG Platform — Product & Technical Reference

> **Version:** 0.1.0 · **Last updated:** May 2026
>
> This document is the single source of truth for understanding, deploying, and operating the RAG Platform. It covers product purpose, architecture, tech stack, database design, API contracts, local development, Docker Compose deployment, and Kubernetes (Helm) deployment. No prior context is required.

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Pod Reference](#3-pod-reference)
   - 3.1 [Backend Pod](#31-backend-pod)
   - 3.2 [Frontend Pod](#32-frontend-pod)
   - 3.3 [Admin-UI Pod](#33-admin-ui-pod)
4. [Tech Stack](#4-tech-stack)
5. [Agentic RAG Pipeline](#5-agentic-rag-pipeline)
6. [MCP Server](#6-mcp-server)
7. [Database Design](#7-database-design)
8. [API Reference](#8-api-reference)
9. [Security Model](#9-security-model)
10. [Local Development](#10-local-development)
11. [Docker Compose Deployment](#11-docker-compose-deployment)
12. [Kubernetes / Helm Deployment](#12-kubernetes--helm-deployment)
13. [Configuration Reference](#13-configuration-reference)
14. [Directory Structure](#14-directory-structure)

---

## 1. Product Overview

The **RAG Platform** is a production-grade, multi-tenant AI chatbot backed by **Agentic Retrieval-Augmented Generation (RAG)**. Unlike a naive RAG system that retrieves once and answers, the platform uses an agent loop — powered by **LangGraph** — that reasons about whether to retrieve, evaluates the quality of what it retrieves, rewrites the query if needed, and only generates an answer once it is confident the context is relevant.

### What it does

| Capability | Detail |
|---|---|
| **Document ingestion** | Upload PDF, TXT, or Markdown files; they are chunked, embedded, and stored in PostgreSQL with pgvector |
| **Hybrid search** | Every query triggers BM25 full-text search and cosine vector search, fused via Reciprocal Rank Fusion (RRF) |
| **Agentic retrieval** | The LLM agent routes queries, grades retrieved chunks, rewrites queries on failure, and loops up to N times before generating |
| **Source citations** | Every answer includes the chunk IDs that grounded it, shown inline in the chat UI |
| **Multi-tenancy** | Organizations are isolated by `org_id`; each org has its own API keys and per-org model/chunk configuration |
| **MCP integration** | Retrieval tools are exposed via Model Context Protocol (MCP), the industry standard for LLM tool interfaces |
| **Admin panel** | Web-based admin for document management, model settings, org config, API key rotation, and analytics |

### Who it is for

- **End users** interact through the **frontend** chat interface
- **Platform administrators** manage the system through the **admin-ui**
- **Developers / integrators** call the **backend** REST API directly or via the MCP server

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Internet / Ingress                             │
└──────────────┬────────────────────────┬────────────────────────┬────────────┘
               │                        │                        │
               ▼                        ▼                        ▼
   ┌───────────────────┐   ┌────────────────────┐   ┌─────────────────────┐
   │   FRONTEND POD    │   │    BACKEND POD      │   │   ADMIN-UI POD      │
   │                   │   │                    │   │                     │
   │  React + Vite     │   │  FastAPI           │   │  FastAPI + Jinja2   │
   │  Tailwind CSS     │   │  LangGraph Agent   │   │  Bootstrap 5        │
   │  Zustand store    │   │  FastMCP Server    │   │  httpx → backend    │
   │  nginx (serve)    │   │  Gemini LLM        │   │                     │
   │                   │   │  Gemini Embeddings │   │  Pages:             │
   │  Chat interface   │   │  pgvector search   │   │  - Dashboard        │
   │  File upload      │   │                    │   │  - Documents        │
   │  Org selector     │   │  Endpoints:        │   │  - Settings         │
   │  History panel    │   │  POST /chat        │   │  - Organizations    │
   │  Source citations │   │  POST /ingest/*    │   │  - Analytics        │
   │                   │   │  GET  /admin/**    │   │                     │
   └─────────┬─────────┘   └────────┬───────────┘   └──────────┬──────────┘
             │                      │                           │
             │  fetch() to backend  │                           │  httpx (internal)
             └──────────────────────┤◄──────────────────────────┘
                                    │
                                    ▼
                      ┌─────────────────────────┐
                      │   PostgreSQL + pgvector  │
                      │                         │
                      │  Tables:                │
                      │  - documents            │
                      │  - chunks (+ HNSW idx)  │
                      │  - organizations        │
                      │  - api_keys             │
                      │  - app_config           │
                      │  - chat_logs            │
                      └─────────────────────────┘
```

### Data flow for a chat message

```
User types question
        │
        ▼
Frontend (React)
  → POST /chat {message, history, org_id, session_id}
        │
        ▼
Backend: LangGraph Agent Loop
  ┌─── router_node ──────────────────────────────────────────────────────────┐
  │    Gemini decides: RETRIEVE or ANSWER directly                           │
  └──────────────────────────────────────────────────────────────────────────┘
        │ RETRIEVE
        ▼
  ┌─── retriever_node ───────────────────────────────────────────────────────┐
  │    Calls FastMCP tool: hybrid_search(query)                              │
  │    → embed query with text-embedding-004 (768d)                          │
  │    → SQL: BM25 rank UNION cosine rank, fused via RRF                     │
  │    Returns top-K chunks with scores                                      │
  └──────────────────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─── grader_node ──────────────────────────────────────────────────────────┐
  │    For each chunk: Gemini rates RELEVANT / IRRELEVANT                    │
  │    If all irrelevant AND loop_count < max_loops → rewrite query          │
  └──────────────────────────────────────────────────────────────────────────┘
        │ RELEVANT
        ▼
  ┌─── generator_node ───────────────────────────────────────────────────────┐
  │    Gemini synthesises answer from relevant chunks                        │
  │    Cites chunk IDs inline                                                │
  └──────────────────────────────────────────────────────────────────────────┘
        │
        ▼
Backend writes row to chat_logs (org_id, session_id, latency, tokens)
        │
        ▼
Response: { answer, source_chunk_ids, loop_count, session_id }
        │
        ▼
Frontend renders MessageBubble + SourceCitations
```

---

## 3. Pod Reference

### 3.1 Backend Pod

**Purpose:** Core application logic. The only service that talks to the database. All other pods consume its REST API.

**Listens on:** `8000`

| Concern | Implementation |
|---|---|
| Web framework | FastAPI 0.115+ |
| Agent orchestration | LangGraph 0.2+ (StateGraph with conditional edges) |
| LLM | Google Gemini 2.0-flash via `google-genai` SDK |
| Embeddings | `text-embedding-004`, 768 dimensions, task-type aware |
| Vector store | PostgreSQL 17 + pgvector extension |
| Full-text search | PostgreSQL `tsvector` + `GIN` index |
| Hybrid search fusion | Reciprocal Rank Fusion (RRF) SQL query |
| MCP server | FastMCP 2.0+ (exposes `hybrid_search`, `ingest_document`, `rerank_results`) |
| Async DB driver | asyncpg 0.29+ (10-20× faster than psycopg2 for concurrent queries) |
| Configuration | Pydantic Settings (env vars + `.env` file) |

**Key source files:**

| File | Purpose |
|---|---|
| `api/main.py` | FastAPI app, CORS middleware, router mounts, `/chat` endpoint |
| `api/admin_router.py` | 22 admin endpoints across 5 groups |
| `api/deps.py` | `X-Admin-Key` header verification (SHA-256 lookup) |
| `agent/graph.py` | LangGraph StateGraph — wires nodes and conditional edges |
| `agent/nodes.py` | 5 node functions: `router`, `retriever`, `grader`, `rewriter`, `generator` |
| `agent/state.py` | `AgentState` TypedDict (messages, docs, loop_count, answer, …) |
| `mcp_server/server.py` | FastMCP server — 3 tools |
| `retrieval/vector_store.py` | `hybrid_search()` — RRF SQL query |
| `embeddings/gemini_embedder.py` | `embed_text()` / `embed_batch()` |
| `ingestion/pipeline.py` | `ingest_file()` / `ingest_text()` — end-to-end ingest |
| `ingestion/chunker.py` | tiktoken-based chunking (300 tokens, 50 overlap) |
| `db/schema.sql` | Base tables: `documents`, `chunks` |
| `db/migrations/001_multitenancy.sql` | `organizations`, `api_keys`, `app_config`, `chat_logs` |
| `config.py` | All settings with defaults |

---

### 3.2 Frontend Pod

**Purpose:** End-user chat interface. Single-page React application served by nginx. Communicates exclusively with the backend REST API.

**Listens on:** `80` (nginx, inside container); mapped to `5173` in Docker Compose

| Concern | Implementation |
|---|---|
| Framework | React 19 + TypeScript |
| Build tool | Vite 8 + `@tailwindcss/vite` |
| Styling | Tailwind CSS v4 (utility classes, no config file) |
| State management | Zustand with `persist` middleware (sessions stored in `localStorage`) |
| Server state | `@tanstack/react-query` (org list fetching) |
| File upload | `react-dropzone` (PDF, TXT, MD) |
| Production server | nginx with SPA fallback (`try_files $uri /index.html`) |
| Build-time config | Vite `VITE_*` environment variables baked in at `docker build` time |

**Component tree:**

```
App
├── QueryClientProvider         (TanStack Query)
├── HistoryPanel                (sidebar: past sessions, "New Chat" button)
├── Header
│   └── OrgSelector             (dropdown: lists orgs from /admin/orgs)
└── ChatWindow
    ├── MessageBubble ×N
    │   └── SourceCitations     (expandable chunk ID list)
    ├── FileUpload              (drag-and-drop ingest zone)
    └── MessageInput            (textarea + send button, Shift+Enter = newline)
```

**State store (`chatStore.ts`):**

| Field | Type | Purpose |
|---|---|---|
| `messages` | `ChatMessage[]` | Current conversation |
| `sessions` | `Session[]` | Persisted past conversations (localStorage, max 50) |
| `activeSessionId` | `string` | UUID of the current session |
| `sessionId` | `string` | Sent to backend for `chat_logs` grouping |
| `activeOrg` | `Org \| null` | Selected organization |

---

### 3.3 Admin-UI Pod

**Purpose:** Internal admin panel for platform operators. Python server-side rendered with Jinja2 templates. Communicates with the backend via internal HTTP (never exposes the database directly).

**Listens on:** `8080`

| Concern | Implementation |
|---|---|
| Framework | FastAPI + Jinja2 templates |
| Styling | Bootstrap 5.3 CDN + Bootstrap Icons (no build step) |
| Charts | Chart.js 4.4 CDN (token usage bar chart) |
| Backend client | `httpx.AsyncClient` singleton with auto-injected `X-Admin-Key` header |
| Configuration | Pydantic Settings (`BACKEND_URL`, `ADMIN_SECRET_KEY`) |

**Pages and routes:**

| Page | Route | What it does |
|---|---|---|
| Dashboard | `GET /` | Summary cards (total chats, tokens, avg latency), recent docs, recent chat logs |
| Documents | `GET /documents` | Paginated document list with chunk counts; inline ingest form |
| Document Detail | `GET /documents/{id}` | Full metadata + first 20 chunk previews |
| Settings | `GET /settings` | Per-org model/chunk config form; changes persist to `app_config` table |
| Organizations | `GET /orgs` | Org table; create org modal |
| Org Detail | `GET /orgs/{id}` | API key list; generate key (raw shown once in alert); revoke key |
| Analytics | `GET /analytics` | Date-filtered summary, daily token bar chart, paginated chat log table |

---

## 4. Tech Stack

### Full dependency matrix

| Layer | Library | Version | Used in |
|---|---|---|---|
| **LLM** | `google-genai` | ≥1.0.0 | Backend |
| **Agent** | `langgraph` | ≥0.2.0 | Backend |
| **Agent (core)** | `langchain-core` | ≥0.3.0 | Backend |
| **MCP server** | `fastmcp` | ≥2.0.0 | Backend |
| **Web API** | `fastapi` | ≥0.115.0 | Backend, Admin-UI |
| **ASGI server** | `uvicorn[standard]` | ≥0.30.0 | Backend, Admin-UI |
| **Async DB** | `asyncpg` | ≥0.29.0 | Backend |
| **pgvector Python** | `pgvector` | ≥0.3.0 | Backend |
| **Settings** | `pydantic-settings` | ≥2.0 | Backend, Admin-UI |
| **Tokenizer** | `tiktoken` | ≥0.7.0 | Backend |
| **PDF parser** | `pypdf2` | ≥3.0.0 | Backend |
| **Templates** | `jinja2` | ≥3.1.0 | Admin-UI |
| **HTTP client** | `httpx` | ≥0.27.0 | Admin-UI |
| **React** | `react` + `react-dom` | 19 | Frontend |
| **Build** | `vite` | 8 | Frontend |
| **CSS** | `tailwindcss` (`@tailwindcss/vite`) | 4 | Frontend |
| **State** | `zustand` | latest | Frontend |
| **Server state** | `@tanstack/react-query` | latest | Frontend |
| **File drop** | `react-dropzone` | latest | Frontend |
| **Database** | PostgreSQL | 17 | Infrastructure |
| **Vector index** | pgvector extension | built-in | Infrastructure |

### Why these choices

| Decision | Reason |
|---|---|
| **google-genai SDK** (not google-generativeai) | The unified SDK — works on both Gemini API and Vertex AI; the legacy SDK is deprecated |
| **LangGraph** (not a simple chain) | Explicit graph structure enables conditional routing, loop detection, and checkpointing; essential for agentic retry loops |
| **FastMCP** | Decorator-based MCP server; auto-generates JSON schema from Python type hints; has built-in inspector UI (`fastmcp dev`) |
| **asyncpg** (not SQLAlchemy) | 10-20× higher QPS than psycopg2; no ORM overhead; pgvector vectors are registered as native types |
| **HNSW index** (not IVFFlat) | No training phase; handles writes without index rebuild; logarithmic query time; cosine ops match normalized Gemini embeddings |
| **RRF fusion** (not score blending) | Rank-based fusion is immune to score scale differences between BM25 and cosine similarity |
| **Jinja2 for admin** (not React) | Admin panel is low-traffic internal tooling; server-rendered HTML requires no frontend build pipeline or API versioning |
| **768d embeddings** (not 1536 or 3072) | Sweet spot: Matryoshka models lose <2% recall at 768d vs 3072d; halves storage and index size |

---

## 5. Agentic RAG Pipeline

### Agent state

```python
class AgentState(TypedDict):
    messages:         list[dict]    # conversation history (accumulating)
    query:            str           # current (possibly rewritten) query
    retrieved_docs:   list[dict]    # chunks from last retrieval
    grading_passed:   bool          # True when grader accepts docs
    loop_count:       int           # number of retrieve-grade iterations
    answer:           str           # final generated answer
    source_chunk_ids: list[int]     # chunk IDs cited in the answer
```

### Graph edges

```
START
  └─► router_node
        ├─ [ANSWER]  ──────────────────────────────────────► generator_node ──► END
        └─ [RETRIEVE] ──► retriever_node
                               └─► grader_node
                                     ├─ [RELEVANT] ─────────► generator_node ──► END
                                     └─ [IRRELEVANT]
                                           ├─ loop_count < max ──► rewriter_node
                                           │                             └─► retriever_node (loop)
                                           └─ loop_count >= max ─────► generator_node ──► END
```

### Node descriptions

**`router_node`**
Sends the user's question to Gemini with a system prompt asking for a single-word verdict: `RETRIEVE` or `ANSWER`. General knowledge questions skip retrieval entirely to save latency.

**`retriever_node`**
Calls `hybrid_search(query)` on the MCP server. The MCP server embeds the query with `text-embedding-004` (task_type=`RETRIEVAL_QUERY`), runs the RRF SQL query, and returns the top-K chunks with their RRF scores.

**`grader_node`**
Issues one Gemini call per retrieved chunk (in parallel via `asyncio.gather`). Each call receives the query and one chunk and returns `RELEVANT` or `IRRELEVANT`. Only relevant chunks are kept. If zero chunks pass and the loop budget remains, routing shifts to the rewriter.

**`rewriter_node`**
Sends the original query to Gemini with a prompt asking for a reformulated version using different keywords. This corrected query replaces `state["query"]` before the next retrieval attempt.

**`generator_node`**
Receives the accepted chunks formatted as `[chunk_id: N]\n{text}` blocks, instructs Gemini to synthesise an answer citing chunk IDs, and writes the answer back to state. If no chunks are available (all loops exhausted), it answers from general knowledge and notes the limitation.

### Hybrid search SQL (RRF)

```sql
WITH bm25 AS (
    SELECT id, text, doc_id,
           ROW_NUMBER() OVER (
               ORDER BY ts_rank(search_vec, plainto_tsquery('english', $1)) DESC
           ) AS rank
    FROM chunks WHERE search_vec @@ plainto_tsquery('english', $1)
    LIMIT 20
),
semantic AS (
    SELECT id, text, doc_id,
           ROW_NUMBER() OVER (ORDER BY embedding <=> $2::vector) AS rank
    FROM chunks ORDER BY embedding <=> $2::vector LIMIT 20
)
SELECT
    COALESCE(b.id, s.id)     AS chunk_id,
    COALESCE(b.text, s.text) AS text,
    1.0/(60 + COALESCE(b.rank, 999)) +
    1.0/(60 + COALESCE(s.rank, 999)) AS rrf_score
FROM bm25 b FULL OUTER JOIN semantic s ON b.id = s.id
ORDER BY rrf_score DESC
LIMIT $3;
```

The constant `60` in the RRF denominator is the standard value from the original RRF paper. It smooths the contribution of low-ranked results and prevents zero-division.

---

## 6. MCP Server

The MCP server runs inside the backend process and is registered as a FastMCP application. It can also be started standalone for debugging:

```bash
fastmcp dev backend/src/rag_chatbot/mcp_server/server.py
# Opens inspector UI at http://localhost:6274
```

### Tools exposed

**`hybrid_search(query: str, top_k: int = 8) → list[dict]`**
Runs the RRF hybrid search described in Section 5. Returns a list of `{chunk_id, doc_id, text, rrf_score}` objects.

**`ingest_document(title: str, text: str, source: str = "") → dict`**
Chunks the provided text, generates embeddings, inserts into `documents` and `chunks` tables. Returns `{doc_id, title, chunks}`.

**`rerank_results(docs: list[dict], query: str, top_k: int = 5) → list[dict]`**
Re-embeds each chunk and the query, computes cosine similarity, returns the top-K chunks sorted by similarity with an added `rerank_score` field. Use this when higher precision matters more than latency.

### Transport

In the current implementation, FastMCP runs in-process with the FastAPI app. For external MCP clients (e.g., Claude Desktop, other LLM agents), the server can be exposed via SSE transport by running it as a separate process and configuring the transport in `server.py`.

---

## 7. Database Design

All tables live in the same PostgreSQL 17 database (`rag_db`). The schema is applied idempotently on every backend startup.

### Entity-relationship overview

```
organizations
    │ 1
    │ ├──────────────── N  api_keys
    │ ├──────────────── N  app_config
    │ ├──────────────── N  chat_logs
    └──────────────────── N  documents
                                │ 1
                                └── N  chunks
```

### Table definitions

#### `documents`
Stores one row per ingested document (file or text blob).

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `title` | `TEXT` | Filename or user-provided title |
| `source` | `TEXT` | File path or URL |
| `metadata` | `JSONB` | Arbitrary key-value pairs |
| `org_id` | `BIGINT FK → organizations` | Added by migration 001; nullable for backwards compatibility |
| `created_at` | `TIMESTAMPTZ` | |

#### `chunks`
One row per text chunk. This is the retrieval unit.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | Referenced as `chunk_id` in API responses |
| `doc_id` | `BIGINT FK → documents` | Cascade delete |
| `chunk_index` | `INT` | Position within the parent document |
| `text` | `TEXT` | Raw chunk text |
| `embedding` | `vector(768)` | Gemini `text-embedding-004` output |
| `search_vec` | `tsvector GENERATED` | Auto-computed from `text` for BM25 search |
| `created_at` | `TIMESTAMPTZ` | |

**Indexes:**

| Index | Type | Purpose |
|---|---|---|
| `idx_chunks_hnsw` | `HNSW (embedding vector_cosine_ops)` | ANN semantic search, m=16, ef_construction=64 |
| `idx_chunks_fts` | `GIN (search_vec)` | Full-text BM25 search |
| `idx_chunks_doc` | `BTREE (doc_id, chunk_index)` | Fast document-level chunk retrieval |

#### `organizations`
Multi-tenancy root. Every other entity belongs to an org.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `name` | `TEXT UNIQUE` | Display name |
| `slug` | `TEXT UNIQUE` | URL-safe identifier (e.g. `acme-corp`) |
| `is_active` | `BOOLEAN` | Soft-delete flag |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

A seed row `('Default', 'default')` is inserted by the migration and is the fallback for all API calls that omit `org_id`.

#### `api_keys`
Per-org API keys for authenticating admin requests.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `org_id` | `BIGINT FK → organizations` | |
| `key_hash` | `TEXT UNIQUE` | **SHA-256 only.** The raw key is never stored. |
| `label` | `TEXT` | Human-readable name (e.g. "Production CI") |
| `is_active` | `BOOLEAN` | Revocation flag |
| `last_used` | `TIMESTAMPTZ` | Updated on each successful auth |
| `created_at` | `TIMESTAMPTZ` | |

Raw key format: `rag_<32 random URL-safe bytes>` (displayed exactly once on creation).

#### `app_config`
Key-value runtime configuration, scoped per org. Overrides the backend `Settings` defaults.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `org_id` | `BIGINT FK → organizations` | |
| `key` | `TEXT` | Config key (see [Configuration Reference](#13-configuration-reference)) |
| `value` | `TEXT` | String representation of the value |
| `updated_at` | `TIMESTAMPTZ` | |

Constraint: `UNIQUE (org_id, key)` — one value per key per org.

#### `chat_logs`
Immutable audit log of every chat interaction.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `org_id` | `BIGINT FK → organizations` | |
| `session_id` | `UUID` | Client-generated; groups messages in a conversation |
| `user_message` | `TEXT` | Raw user input |
| `assistant_response` | `TEXT` | Final generated answer |
| `source_chunk_ids` | `BIGINT[]` | Chunks cited in the answer |
| `loop_count` | `INT` | How many retrieval loops ran |
| `prompt_tokens` | `INT` | Reserved (populated when Gemini reports usage) |
| `completion_tokens` | `INT` | Reserved |
| `latency_ms` | `INT` | Wall-clock time from request receipt to response |
| `created_at` | `TIMESTAMPTZ` | |

---

## 8. API Reference

### Public endpoints (no auth)

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/chat` | `{message, history?, org_id?, session_id?}` | `{answer, source_chunk_ids, loop_count, session_id}` |
| `POST` | `/ingest/text` | `{title, text, source?}` | `{doc_id, title, chunks}` |
| `POST` | `/ingest/file` | `multipart/form-data` with `file` field | `{doc_id, title, chunks}` |
| `GET` | `/health` | — | `{"status": "ok"}` |

#### `POST /chat`

```json
// Request
{
  "message": "What are the key features of the RAG pipeline?",
  "history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"}
  ],
  "org_id": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}

// Response
{
  "answer": "The RAG pipeline consists of… [chunk_id: 42]",
  "source_chunk_ids": [42, 51, 67],
  "loop_count": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

`history` is the full conversation so the model has context. `session_id` is optional — if omitted, the backend generates one. `org_id` defaults to the `default` org.

---

### Admin endpoints (require `X-Admin-Key` header)

All admin endpoints are prefixed with `/admin`. Authentication is via the `X-Admin-Key` HTTP header. The value must match either the `ADMIN_SECRET_KEY` environment variable (bootstrap) or a live row in the `api_keys` table (production).

#### Organizations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/orgs` | List all organizations |
| `POST` | `/admin/orgs` | Create org `{name, slug}` |
| `GET` | `/admin/orgs/{id}` | Get org with current config snapshot |
| `PATCH` | `/admin/orgs/{id}` | Update `name` or `is_active` |
| `DELETE` | `/admin/orgs/{id}` | Soft-delete (sets `is_active=false`) |

#### API Keys

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/orgs/{id}/keys` | List keys (hash never returned) |
| `POST` | `/admin/orgs/{id}/keys` | Generate key — **raw key shown in response once only** |
| `DELETE` | `/admin/orgs/{id}/keys/{key_id}` | Revoke key |

#### Documents

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/docs` | Paginated list with chunk counts `?org_id=&page=&limit=` |
| `GET` | `/admin/docs/{id}` | Document metadata + chunk preview |
| `DELETE` | `/admin/docs/{id}` | Hard delete (cascades to chunks) |
| `POST` | `/admin/docs/ingest/text` | `{title, text, source, org_id}` |
| `POST` | `/admin/docs/ingest/file` | Multipart upload `?org_id=` |

#### Configuration

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/config` | All config for org `?org_id=` |
| `PUT` | `/admin/config` | Bulk upsert `{org_id, settings: {key: value}}` |
| `GET` | `/admin/config/{key}` | Single setting `?org_id=` |

#### Analytics

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/analytics/summary` | Totals and avg latency `?org_id=&from_dt=&to_dt=` |
| `GET` | `/admin/analytics/logs` | Paginated chat logs |
| `GET` | `/admin/analytics/logs/{id}` | Full single log entry |
| `GET` | `/admin/analytics/token-usage` | Daily rollup `?org_id=&days=30` |

#### System

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/system/health` | Extended health: DB pool, env info |
| `POST` | `/admin/system/schema/migrate` | Apply schema + migration 001 on-demand |

---

## 9. Security Model

### Authentication layers

| Layer | Mechanism | Coverage |
|---|---|---|
| **Admin API** | `X-Admin-Key` header, SHA-256 hash compared against `api_keys` table | All `/admin/**` endpoints |
| **Bootstrap** | Static `ADMIN_SECRET_KEY` env var | Used before any org/key rows exist; must be rotated in production |
| **CORS** | FastAPI `CORSMiddleware` with explicit `CORS_ORIGINS` allow-list | Prevents cross-origin chat requests |
| **Ingress restriction** | `nginx.ingress.kubernetes.io/whitelist-source-range` on admin-ui ingress | Limits admin panel to internal network CIDR |

### Secrets handling

| Secret | Where stored | Never in |
|---|---|---|
| `GEMINI_API_KEY` | Environment variable / Kubernetes Secret | Code, logs, API responses |
| `DATABASE_URL` | Environment variable / Kubernetes Secret | Code, logs, API responses |
| `ADMIN_SECRET_KEY` | Environment variable / Kubernetes Secret | Code, git history |
| Raw API keys | Shown once in create-key response | Database (SHA-256 hash only is stored) |

### Internal traffic

In Docker Compose, `admin-ui` reaches the backend at `http://backend:8000` over the Docker internal bridge — traffic never leaves the machine. In Kubernetes, admin-ui uses the ClusterIP service DNS `http://rag-backend:8000` — traffic stays within the cluster and never traverses a public ingress.

---

## 10. Local Development

### Prerequisites

- Docker Desktop (for PostgreSQL)
- Python ≥ 3.10
- Node.js 22
- A Gemini API key from [aistudio.google.com](https://aistudio.google.com)

### Step 1 — Environment file

```bash
cd rag-platform
cp .env.example .env
```

Edit `.env`:

```env
GEMINI_API_KEY=your-key-here
ADMIN_SECRET_KEY=my-local-secret
```

### Step 2 — Start PostgreSQL

```bash
docker compose up postgres -d
```

Wait for the health check to go green (about 5 seconds):

```bash
docker compose ps
# rag_postgres   Up (healthy)
```

### Step 3 — Run the backend

```bash
cd backend
pip install -e ".[dev]"

# Apply schema (also runs automatically on uvicorn startup)
python -m rag_chatbot.db.connection

# Start the server
uvicorn rag_chatbot.api.main:app --reload
# Listening on http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

### Step 4 — Run the admin-ui

```bash
# In a new terminal
cd admin-ui
pip install -e .
BACKEND_URL=http://localhost:8000 ADMIN_SECRET_KEY=my-local-secret \
  uvicorn admin_ui.main:app --port 8080 --reload
# Open http://localhost:8080
```

### Step 5 — Run the frontend

```bash
# In a new terminal
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
# Open http://localhost:5173
```

### Step 6 — Ingest a document and chat

```bash
# Ingest text via curl
curl -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Doc", "text": "The capital of France is Paris. Paris is known for the Eiffel Tower."}'

# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the capital of France?"}'
```

### Step 7 — Inspect MCP tools (optional)

```bash
cd backend
fastmcp dev src/rag_chatbot/mcp_server/server.py
# Opens MCP Inspector at http://localhost:6274
# Call hybrid_search, ingest_document, or rerank_results interactively
```

---

## 11. Docker Compose Deployment

Docker Compose is the recommended approach for staging, demos, and single-server production deployments.

### Service graph

```
postgres  ←── backend  ←──┬── frontend
                          └── admin-ui
```

`backend` waits for `postgres` to be healthy before starting. `frontend` and `admin-ui` wait for `backend` to be healthy.

### Starting the full stack

```bash
cd rag-platform
cp .env.example .env   # fill in GEMINI_API_KEY and ADMIN_SECRET_KEY

docker compose up --build
```

The first build takes 2-4 minutes (downloads base images, installs dependencies). Subsequent starts use the build cache.

### Service URLs

| Service | URL | Notes |
|---|---|---|
| Frontend (chat) | http://localhost:5173 | React SPA served by nginx |
| Admin UI | http://localhost:8080 | FastAPI + Jinja2 admin panel |
| Backend API | http://localhost:8000 | REST API; Swagger at `/docs` |
| Backend API | http://localhost:8000/docs | Interactive Swagger UI |
| PostgreSQL | localhost:5432 | `rag:rag_secret@rag_db` |

### Individual service commands

```bash
# Rebuild only the backend (after code changes)
docker compose up backend --build

# View backend logs
docker compose logs -f backend

# Apply DB migrations manually
docker compose exec backend python -m rag_chatbot.db.connection

# Open a psql shell
docker compose exec postgres psql -U rag -d rag_db
```

### Stopping and cleaning up

```bash
docker compose down           # stops containers, keeps volumes
docker compose down -v        # stops containers AND deletes DB volume
```

### Environment variables (Docker Compose)

| Variable | Set in | Description |
|---|---|---|
| `GEMINI_API_KEY` | Root `.env` | Google Gemini API key |
| `ADMIN_SECRET_KEY` | Root `.env` | Bootstrap admin key (default: `change-me`) |
| `DATABASE_URL` | Hardcoded in compose | `postgresql://rag:rag_secret@postgres:5432/rag_db` |
| `CORS_ORIGINS` | Hardcoded in compose | `["http://localhost:5173","http://localhost:8080"]` |
| `VITE_API_BASE_URL` | Build arg in compose | `http://localhost:8000` (baked into frontend at build time) |
| `BACKEND_URL` | Compose env for admin-ui | `http://backend:8000` (internal Docker DNS) |

---

## 12. Kubernetes / Helm Deployment

Each pod has its own Helm chart under `helm/`. They are deployed independently, which allows separate image builds, rollouts, and resource scaling.

### Prerequisites

- A Kubernetes cluster (EKS, GKE, AKS, or k3d/minikube for local)
- `helm` ≥ 3.14
- `kubectl` configured for your cluster
- nginx ingress controller installed in the cluster
- A PostgreSQL instance accessible from the cluster (e.g., Amazon RDS, Cloud SQL, or a Helm-managed PostgreSQL)

### Chart overview

| Chart | Path | Default host |
|---|---|---|
| `rag-backend` | `helm/backend/` | `api.rag.example.com` |
| `rag-frontend` | `helm/frontend/` | `chat.rag.example.com` |
| `rag-admin-ui` | `helm/admin-ui/` | `admin.rag.example.com` |

### Step 1 — Build and push images

```bash
# Backend
docker build -t ghcr.io/your-org/rag-backend:v1.0.0 ./backend
docker push ghcr.io/your-org/rag-backend:v1.0.0

# Frontend (pass the production API URL as a build arg)
docker build \
  --build-arg VITE_API_BASE_URL=https://api.rag.example.com \
  --build-arg VITE_ADMIN_KEY=your-admin-key \
  -t ghcr.io/your-org/rag-frontend:v1.0.0 ./frontend
docker push ghcr.io/your-org/rag-frontend:v1.0.0

# Admin UI
docker build -t ghcr.io/your-org/rag-admin-ui:v1.0.0 ./admin-ui
docker push ghcr.io/your-org/rag-admin-ui:v1.0.0
```

### Step 2 — Configure values

Copy and edit each chart's `values.yaml`:

**`helm/backend/values.yaml` — key fields to set:**

```yaml
image:
  repository: ghcr.io/your-org/rag-backend
  tag: "v1.0.0"

ingress:
  host: api.rag.example.com
  tlsSecret: rag-backend-tls    # name of the TLS Secret in k8s

env:
  APP_ENV: production
  CORS_ORIGINS: '["https://chat.rag.example.com","https://admin.rag.example.com"]'

secrets:
  GEMINI_API_KEY: "your-gemini-api-key"
  DATABASE_URL: "postgresql://user:pass@rds-host:5432/rag_db"
  ADMIN_SECRET_KEY: "your-production-secret"
```

**`helm/frontend/values.yaml` — key fields:**

```yaml
image:
  repository: ghcr.io/your-org/rag-frontend
  tag: "v1.0.0"

ingress:
  host: chat.rag.example.com
  tlsSecret: rag-frontend-tls
```

> Note: `VITE_API_BASE_URL` is baked into the frontend image at build time (step 1), not set here.

**`helm/admin-ui/values.yaml` — key fields:**

```yaml
image:
  repository: ghcr.io/your-org/rag-admin-ui
  tag: "v1.0.0"

ingress:
  host: admin.rag.example.com
  tlsSecret: rag-admin-tls
  whitelistSourceRange: "10.0.0.0/8"   # your VPN/office CIDR

env:
  BACKEND_URL: http://rag-backend:8000  # internal k8s ClusterIP DNS

secrets:
  ADMIN_SECRET_KEY: "your-production-secret"
```

### Step 3 — Apply DB migrations

Before deploying, apply the schema to your production database:

```bash
# Port-forward to run migrations from your local machine
kubectl run pg-client --image=postgres:17 --rm -it --restart=Never -- \
  psql postgresql://user:pass@rds-host:5432/rag_db \
  -f helm/backend/…   # or copy-paste schema.sql + 001_multitenancy.sql
```

Or use the `/admin/system/schema/migrate` endpoint after the backend is deployed (requires `X-Admin-Key`).

### Step 4 — Deploy

```bash
# Backend (deploy first — frontend and admin-ui depend on it)
helm upgrade --install rag-backend helm/backend/ \
  --namespace rag --create-namespace \
  --values helm/backend/values.yaml

# Frontend
helm upgrade --install rag-frontend helm/frontend/ \
  --namespace rag \
  --values helm/frontend/values.yaml

# Admin UI
helm upgrade --install rag-admin helm/admin-ui/ \
  --namespace rag \
  --values helm/admin-ui/values.yaml
```

### Step 5 — Verify

```bash
kubectl get pods -n rag
# NAME                              READY   STATUS    RESTARTS
# rag-backend-7d6f9b-xxxx           1/1     Running   0
# rag-backend-7d6f9b-yyyy           1/1     Running   0   ← 2 replicas
# rag-frontend-5c8b4d-xxxx          1/1     Running   0
# rag-frontend-5c8b4d-yyyy          1/1     Running   0
# rag-admin-ui-3a2f1c-xxxx          1/1     Running   0

kubectl get ingress -n rag
# NAME            CLASS   HOSTS                       ADDRESS
# rag-backend     nginx   api.rag.example.com         x.x.x.x
# rag-frontend    nginx   chat.rag.example.com        x.x.x.x
# rag-admin-ui    nginx   admin.rag.example.com       x.x.x.x

# Test the backend health
curl https://api.rag.example.com/health
# {"status": "ok"}
```

### Horizontal Pod Autoscaling (backend only)

The backend chart includes an HPA resource:

```yaml
hpa:
  enabled: true
  minReplicas: 2
  maxReplicas: 6
  targetCPUUtilizationPercentage: 70
```

The backend scales between 2 and 6 replicas based on CPU utilisation. The frontend is stateless nginx and scales manually. The admin-ui runs as a single replica (low-traffic internal tool).

### Rolling updates

```bash
# Update backend to a new image
helm upgrade rag-backend helm/backend/ \
  --namespace rag \
  --set image.tag=v1.1.0
```

Kubernetes performs a rolling update — new pods start before old ones stop, so there is zero downtime.

---

## 13. Configuration Reference

### Backend environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | — | Google AI Studio or Vertex AI API key |
| `DATABASE_URL` | **Yes** | — | PostgreSQL DSN: `postgresql://user:pass@host:5432/db` |
| `ADMIN_SECRET_KEY` | No | `change-me` | Bootstrap admin key. **Must be changed in production.** |
| `CORS_ORIGINS` | No | `["http://localhost:5173", "http://localhost:8080"]` | JSON array of allowed origins |
| `APP_ENV` | No | `development` | `development` or `production` |
| `LLM_MODEL` | No | `gemini-2.0-flash` | Gemini model for generation and grading |
| `EMBEDDING_MODEL` | No | `text-embedding-004` | Gemini embedding model |
| `EMBEDDING_DIM` | No | `768` | Embedding output dimensions (768 / 1536 / 3072) |
| `RETRIEVAL_TOP_K` | No | `8` | Chunks returned per hybrid search |
| `GRADER_MAX_LOOPS` | No | `3` | Maximum retrieve-grade iterations before fallback |
| `CHUNK_SIZE` | No | `300` | Chunk size in tokens |
| `CHUNK_OVERLAP` | No | `50` | Overlap between consecutive chunks in tokens |

### Per-org runtime config (`app_config` table)

These values can be changed per-org at runtime via the admin UI or `PUT /admin/config` without redeployment:

| Key | Default | Description |
|---|---|---|
| `llm_model` | `gemini-2.0-flash` | LLM model for this org |
| `embedding_model` | `text-embedding-004` | Embedding model for this org |
| `embedding_dim` | `768` | Embedding dimension for this org |
| `retrieval_top_k` | `8` | Top-K chunks for this org |
| `grader_max_loops` | `3` | Max grader loops for this org |
| `chunk_size` | `300` | Chunk size for new ingestions |
| `chunk_overlap` | `50` | Chunk overlap for new ingestions |

> **Note:** Changing `embedding_dim` or `embedding_model` does not re-embed existing chunks. Re-ingest affected documents after changing embedding settings.

### Admin-UI environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BACKEND_URL` | **Yes** | `http://localhost:8000` | URL of the backend pod (internal DNS in Kubernetes) |
| `ADMIN_SECRET_KEY` | **Yes** | `change-me` | Must match the backend's `ADMIN_SECRET_KEY` |
| `APP_ENV` | No | `development` | `development` or `production` |

### Frontend build-time variables

These are set as Docker `--build-arg` values and baked into the static bundle at build time. They **cannot** be changed after the image is built.

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL called by the browser |
| `VITE_ADMIN_KEY` | `change-me` | Admin key used to fetch the org list from `/admin/orgs` |

---

## 14. Directory Structure

```
rag-platform/
│
├── .env.example                   Root: GEMINI_API_KEY, ADMIN_SECRET_KEY
├── docker-compose.yml             All 4 services + volumes
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml             Python deps (google-genai, langgraph, fastmcp, asyncpg…)
│   └── src/rag_chatbot/
│       ├── config.py              Pydantic Settings
│       ├── api/
│       │   ├── main.py            FastAPI app, CORS, router mounts, /chat endpoint
│       │   ├── admin_router.py    22 admin endpoints (orgs, docs, config, analytics, system)
│       │   └── deps.py            X-Admin-Key verification
│       ├── agent/
│       │   ├── state.py           AgentState TypedDict
│       │   ├── nodes.py           router, retriever, grader, rewriter, generator
│       │   └── graph.py           LangGraph StateGraph + conditional edges
│       ├── mcp_server/
│       │   └── server.py          FastMCP: hybrid_search, ingest_document, rerank_results
│       ├── retrieval/
│       │   └── vector_store.py    hybrid_search() RRF SQL
│       ├── embeddings/
│       │   └── gemini_embedder.py embed_text(), embed_batch()
│       ├── ingestion/
│       │   ├── loader.py          PDF / TXT / MD → raw text
│       │   ├── chunker.py         tiktoken chunking
│       │   └── pipeline.py        ingest_file(), ingest_text()
│       └── db/
│           ├── connection.py      asyncpg pool, pgvector codec registration
│           ├── schema.sql         documents, chunks tables + indexes
│           └── migrations/
│               └── 001_multitenancy.sql   organizations, api_keys, app_config, chat_logs
│
├── frontend/
│   ├── Dockerfile                 Multi-stage: node builder → nginx
│   ├── nginx.conf                 SPA fallback (try_files → /index.html)
│   ├── vite.config.ts             Vite + React + Tailwind plugin
│   └── src/
│       ├── App.tsx                Root: QueryClientProvider, layout
│       ├── types/index.ts         ChatMessage, Org, Session, ChatResponse
│       ├── api/client.ts          sendChat(), ingestFile(), listOrgs()
│       ├── store/chatStore.ts     Zustand store with localStorage persistence
│       ├── hooks/useChat.ts       send(), loading, error state
│       └── components/
│           ├── ChatWindow.tsx     Scrollable message list + upload toggle
│           ├── MessageBubble.tsx  User / assistant bubble with timestamp
│           ├── MessageInput.tsx   Textarea, Enter-to-send, spinner
│           ├── SourceCitations.tsx Expandable chunk ID list
│           ├── FileUpload.tsx     react-dropzone PDF/TXT/MD ingest
│           ├── OrgSelector.tsx    Org dropdown (fetches /admin/orgs)
│           └── HistoryPanel.tsx   Session history sidebar
│
├── admin-ui/
│   ├── Dockerfile
│   ├── pyproject.toml             Python deps (fastapi, jinja2, httpx…)
│   └── src/admin_ui/
│       ├── main.py                FastAPI app, Jinja2 mount, middleware
│       ├── config.py              Settings (BACKEND_URL, ADMIN_SECRET_KEY)
│       ├── client.py              httpx async wrapper for all backend calls
│       ├── routers/
│       │   ├── dashboard.py       GET /
│       │   ├── documents.py       GET/POST/DELETE /documents
│       │   ├── settings.py        GET/POST /settings
│       │   ├── orgs.py            GET/POST /orgs, key management
│       │   └── analytics.py       GET /analytics
│       └── templates/
│           ├── base.html          Bootstrap 5, sidebar nav, flash messages
│           ├── dashboard.html     Summary cards, recent docs/logs
│           ├── documents.html     Table + ingest form
│           ├── document_detail.html Metadata + chunk preview
│           ├── settings.html      Per-org config form
│           ├── orgs.html          Org table + create modal
│           ├── org_detail.html    API key management
│           └── analytics.html     Token chart (Chart.js) + log table
│
└── helm/
    ├── backend/
    │   ├── Chart.yaml
    │   ├── values.yaml            replicaCount, image, ingress, resources, hpa, secrets
    │   └── templates/
    │       ├── deployment.yaml    2 replicas, health probes, envFrom
    │       ├── service.yaml       ClusterIP :8000
    │       ├── ingress.yaml       nginx, TLS, 50 MB body size
    │       ├── configmap.yaml     Non-secret env vars
    │       ├── secret.yaml        GEMINI_API_KEY, DATABASE_URL, ADMIN_SECRET_KEY
    │       └── hpa.yaml           Scale 2-6 at 70% CPU
    ├── frontend/
    │   ├── Chart.yaml
    │   ├── values.yaml            replicaCount, image, ingress
    │   └── templates/
    │       ├── deployment.yaml    2 replicas, nginx health probes
    │       ├── service.yaml       ClusterIP :80
    │       └── ingress.yaml       nginx, TLS
    └── admin-ui/
        ├── Chart.yaml
        ├── values.yaml            1 replica, ingress with IP whitelist, BACKEND_URL
        └── templates/
            ├── deployment.yaml    1 replica, health probes, envFrom
            ├── service.yaml       ClusterIP :8080
            ├── ingress.yaml       nginx, TLS, IP source whitelist
            ├── configmap.yaml     BACKEND_URL, APP_ENV
            └── secret.yaml        ADMIN_SECRET_KEY
```

---

*End of document.*
