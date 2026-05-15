# RAG Platform — Product & Technical Reference

> **Version:** 0.3.0 · **Last updated:** May 2026
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
6. [Conversational Context](#6-conversational-context)
7. [Multi-LLM Provider Support](#7-multi-llm-provider-support)
8. [Streaming Chat](#8-streaming-chat)
9. [SSO & Identity (Zitadel)](#9-sso--identity-zitadel)
10. [Observability (Langfuse v3)](#10-observability-langfuse-v3)
11. [MCP Server](#11-mcp-server)
12. [Database Design](#12-database-design)
13. [API Reference](#13-api-reference)
14. [Security Model](#14-security-model)
15. [Local Development](#15-local-development)
16. [Docker Compose Deployment](#16-docker-compose-deployment)
17. [Kubernetes / Helm Deployment](#17-kubernetes--helm-deployment)
18. [Configuration Reference](#18-configuration-reference)
19. [Directory Structure](#19-directory-structure)

---

## 1. Product Overview

The **RAG Platform** is a production-grade, multi-tenant AI chatbot backed by **Agentic Retrieval-Augmented Generation (RAG)**. Unlike a naive RAG system that retrieves once and answers, the platform uses an agent loop — powered by **LangGraph** — that reasons about whether to retrieve, evaluates the quality of what it retrieves, rewrites the query if needed, resolves follow-up questions using conversation history, and only generates an answer once it is confident the context is relevant.

### What it does

| Capability | Detail |
|---|---|
| **Conversational context** | Follow-up questions like "tell me more about that" are automatically rewritten into standalone queries using the last 3 conversation exchanges before retrieval runs |
| **Document ingestion** | Upload PDF, TXT, or Markdown files; they are chunked, embedded, and stored in PostgreSQL with pgvector |
| **Hybrid search** | Every query triggers BM25 full-text search and cosine vector search, fused via Reciprocal Rank Fusion (RRF) |
| **Agentic retrieval** | The LLM agent routes queries, grades retrieved chunks, rewrites queries on failure, and loops up to N times before generating |
| **Knowledge grounding** | A strict grader passes only chunks that directly answer the query; when no relevant chunks are found after all retries, a dedicated `clarify_node` asks for more context instead of hallucinating |
| **KB overview intent** | When a user asks "what's in the knowledge base?", a dedicated node summarises all document titles — bypassing retrieval entirely |
| **Streaming responses** | Token-by-token streaming via `POST /chat/stream` using LangGraph `astream_events` + SSE; the frontend renders tokens in real time |
| **Multi-LLM support** | Pluggable LLM backend: Gemini (default), Anthropic Claude, or any NVIDIA NIM / OpenAI-compatible endpoint (Groq, Ollama, Together AI) |
| **Source citations** | Every answer includes the source documents that grounded it, shown inline in the chat UI |
| **User feedback** | Thumbs-up / thumbs-down on each assistant message; feedback stored against the `chat_logs` row via `POST /chat/feedback/{log_id}` |
| **Follow-up suggestions** | After each assistant response, three contextual follow-up question chips are surfaced asynchronously |
| **Multi-tenancy** | Organizations are isolated by `org_id`; each org has its own API keys and per-org model/chunk configuration |
| **SSO via Zitadel** | Enterprise OIDC SSO with role-based access control; org membership resolved from JWT claims |
| **OBO token exchange** | Authenticated users get a per-user ServiceNow token via On-Behalf-Of flow, enabling permission-aware live KB searches that respect ServiceNow ACLs |
| **Admin authentication** | Admin-ui login backed by the backend user database; only `superadmin` and `admin` roles are admitted |
| **Persistent org scope** | Admin panel org selection stored in a signed httponly cookie — survives page navigations and redirects |
| **Observability** | Langfuse v3 tracing for every LangGraph node, LLM call, and retrieval step with user/session/org attribution |
| **Rate limiting** | Per-IP rate limiting on all chat and ingest endpoints via `slowapi` |
| **Connector support** | ServiceNow, SharePoint, Confluence, Google Drive, Zendesk, and Jira connectors for automated knowledge sync |
| **MCP integration** | Retrieval tools exposed via Model Context Protocol (MCP) for integration with Claude Desktop and other LLM agents |
| **Admin panel** | Web-based admin for document management, model settings, org config, API key rotation, analytics, connector management, and SSO role assignment |

### Who it is for

- **End users** interact through the **frontend** chat interface
- **Platform administrators** manage the system through the **admin-ui**
- **Developers / integrators** call the **backend** REST API directly or via the MCP server

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Internet / Ingress                                 │
└──────────────┬────────────────────────┬────────────────────────┬────────────────┘
               │                        │                        │
               ▼                        ▼                        ▼
   ┌───────────────────┐   ┌────────────────────┐   ┌─────────────────────┐
   │   FRONTEND POD    │   │    BACKEND POD      │   │   ADMIN-UI POD      │
   │                   │   │                    │   │                     │
   │  React + Vite     │   │  FastAPI           │   │  FastAPI + Jinja2   │
   │  Tailwind CSS     │   │  LangGraph Agent   │   │  Bootstrap 5        │
   │  Zustand store    │   │  FastMCP Server    │   │  httpx → backend    │
   │  nginx (serve)    │   │  Multi-LLM client  │   │                     │
   │                   │   │  Gemini Embeddings │   │  Pages:             │
   │  Features:        │   │  pgvector search   │   │  - Dashboard        │
   │  - Streaming chat │   │  Rate limiter      │   │  - Documents        │
   │  - History panel  │   │                    │   │  - Settings         │
   │  - Source cites   │   │  Endpoints:        │   │  - Organizations    │
   │  - Feedback       │   │  POST /chat        │   │  - Analytics        │
   │  - File upload    │   │  POST /chat/stream │   │  - Connectors       │
   │  - Org selector   │   │  POST /ingest/*    │   │  - SSO role mgmt    │
   │                   │   │  GET  /admin/**    │   │                     │
   └─────────┬─────────┘   └────────┬───────────┘   └──────────┬──────────┘
             │                      │                           │
             │  fetch() / SSE       │                           │  httpx (internal)
             └──────────────────────┤◄──────────────────────────┘
                                    │
                        ┌───────────┴───────────┐
                        │                       │
                        ▼                       ▼
          ┌─────────────────────────┐  ┌────────────────────────┐
          │   PostgreSQL + pgvector  │  │   Zitadel (OIDC IdP)   │
          │                         │  │                        │
          │  Tables:                │  │  - SSO login           │
          │  - documents            │  │  - Org claims          │
          │  - chunks (+ HNSW idx)  │  │  - RBAC roles          │
          │  - organizations        │  │  - OBO token exchange  │
          │  - api_keys             │  │                        │
          │  - app_config           │  └────────────────────────┘
          │  - chat_logs            │
          │  - users                │  ┌────────────────────────┐
          │  - connectors           │  │   Langfuse v3          │
          └─────────────────────────┘  │                        │
                                       │  - ClickHouse (traces) │
                                       │  - Redis (job queue)   │
                                       │  - MinIO (events/S3)   │
                                       │  - langfuse-worker     │
                                       │                        │
                                       └────────────────────────┘
```

### Data flow for a streaming chat message

```
User types question
        │
        ▼
Frontend (React) — SSE connection
  → POST /chat/stream {message, history, org_id, session_id}
        │
        ▼
Backend: Langfuse propagates user_id + session_id + org tag
  → LangGraph astream_events
        │
        ▼
  ┌─── contextualize_node ──────────────────────────────────────────────────────┐
  │    If follow-up: uses last 3 turns to rewrite as standalone question        │
  │    First turn: passes query through unchanged                                │
  └──────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─── intent_node ─────────────────────────────────────────────────────────────┐
  │    Regex check: chitchat → skip_retrieval; KB overview → kb_overview node   │
  └──────────────────────────────────────────────────────────────────────────────┘
        │ RETRIEVE
        ▼
  ┌─── retriever_node ──────────────────────────────────────────────────────────┐
  │    Hybrid search (BM25 + cosine RRF)                                        │
  │    OBO supplement: if Zitadel token → exchange → live ServiceNow search     │
  └──────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─── grader_node ─────────────────────────────────────────────────────────────┐
  │    Single batched LLM call grades all chunks; returns relevant indices       │
  │    If all irrelevant AND loop_count < max_loops → rewriter_node             │
  └──────────────────────────────────────────────────────────────────────────────┘
        │ RELEVANT
        ▼
  ┌─── generator_node ──────────────────────────────────────────────────────────┐
  │    Injects conversation history + context chunks into prompt                 │
  │    Streams tokens via adispatch_custom_event → SSE to browser                │
  └──────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
Backend writes chat_logs row; Langfuse trace ends
        │
        ▼
Frontend renders tokens in real time; source citations appear on completion
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
| LLM | Pluggable: Gemini (default), Anthropic, NVIDIA NIM / OpenAI-compatible |
| Embeddings | `text-embedding-004`, 768 dimensions, task-type aware |
| Vector store | PostgreSQL 17 + pgvector extension |
| Full-text search | PostgreSQL `tsvector` + `GIN` index |
| Hybrid search fusion | Reciprocal Rank Fusion (RRF) SQL query |
| Streaming | LangGraph `astream_events` + FastAPI `StreamingResponse` (SSE) |
| MCP server | FastMCP 2.0+ |
| Async DB driver | asyncpg 0.29+ |
| Rate limiting | slowapi (per-IP, 20 req/min on chat endpoints) |
| Identity | Zitadel OIDC JWT validation + OBO token exchange |
| Observability | Langfuse v4 SDK (traces, generations, retrievals) |
| Configuration | Pydantic Settings (env vars + `.env` file) |

**Key source files:**

| File | Purpose |
|---|---|
| `api/main.py` | FastAPI app, `/chat`, `/chat/stream`, `/chat/feedback`, auth middleware |
| `api/admin_router.py` | Admin endpoints (orgs, docs, config, analytics, system) |
| `api/deps.py` | JWT + `X-Admin-Key` verification; `require_user()`, `extract_zitadel_token()` |
| `agent/graph.py` | LangGraph StateGraph — wires all 8 nodes and conditional edges |
| `agent/nodes.py` | `contextualize`, `intent`, `retriever`, `grader`, `rewriter`, `generator`, `clarify`, `kb_overview` |
| `agent/state.py` | `AgentState` TypedDict |
| `llm/client.py` | Unified multi-LLM client: `generate()` + `stream_generate()` |
| `observability.py` | Langfuse v4 singleton + `get_langfuse()` |
| `retrieval/vector_store.py` | `hybrid_search()` — RRF SQL, org-scoped, dedup by `external_id` |
| `connectors/snow_token_exchange.py` | Zitadel → ServiceNow OBO token exchange |
| `auth/router.py` | `/auth/login`, `/auth/me`, `/auth/logout` |

---

### 3.2 Frontend Pod

**Purpose:** End-user chat interface. Single-page React application served by nginx. Communicates with the backend via REST and SSE.

**Listens on:** `80` (nginx, inside container); mapped to `5173` in Docker Compose

| Concern | Implementation |
|---|---|
| Framework | React 19 + TypeScript |
| Build tool | Vite 8 + `@tailwindcss/vite` |
| Styling | Tailwind CSS v4 |
| State management | Zustand with `persist` middleware (sessions stored in `localStorage`) |
| Server state | `@tanstack/react-query` |
| File upload | `react-dropzone` |
| Streaming | `EventSource` + `ReadableStream` for SSE token-by-token rendering |
| Production server | nginx with SPA fallback |

**Component tree:**

```
App
├── QueryClientProvider
├── HistoryPanel         (sidebar: past sessions, "New Chat" button)
├── Header
│   └── OrgSelector      (dropdown: lists orgs from /admin/orgs)
└── ChatWindow
    ├── MessageBubble ×N
    │   ├── SourceCitations    (expandable source list)
    │   └── FeedbackButtons    (thumbs up / thumbs down)
    ├── FileUpload             (drag-and-drop ingest zone)
    └── MessageInput           (textarea + send button)
```

**State store (`chatStore.ts`):**

| Field | Type | Purpose |
|---|---|---|
| `messages` | `ChatMessage[]` | Current conversation (includes `logId` for feedback) |
| `sessions` | `Session[]` | Persisted past conversations (localStorage, max 50) |
| `activeSessionId` | `string` | UUID of the current session |
| `activeOrg` | `Org \| null` | Selected organization |

---

### 3.3 Admin-UI Pod

**Purpose:** Internal admin panel for platform operators. Python server-side rendered with Jinja2. Communicates with the backend via internal HTTP.

**Listens on:** `8080`

| Concern | Implementation |
|---|---|
| Framework | FastAPI + Jinja2 templates |
| Styling | Bootstrap 5.3 CDN + Bootstrap Icons |
| Charts | Chart.js 4.4 CDN |
| Backend client | `httpx.AsyncClient` with auto-injected `X-Admin-Key` |
| Authentication | Starlette `SessionMiddleware`; login validates against backend `/auth/login`; `superadmin` / `admin` roles only; 8-hour signed cookie |
| Org scope | `admin_org_scope` httponly cookie; middleware syncs on every response |

**Pages and routes:**

| Page | Route | What it does |
|---|---|---|
| Login | `GET/POST /login` | Email + password; backend auth; role enforcement |
| Dashboard | `GET /` | Summary cards, recent docs, recent chat logs |
| Documents | `GET /documents` | Paginated list + inline ingest form |
| Document Detail | `GET /documents/{id}` | Full metadata + chunk preview |
| Settings | `GET /settings` | Per-org LLM/chunk/provider config form |
| Organizations | `GET /orgs` | Org table; create org modal |
| Org Detail | `GET /orgs/{id}` | API keys + SSO role assignments |
| Analytics | `GET /analytics` | Date-filtered summary, token chart, chat log table |
| Connectors | `GET /connectors` | Status of all connectors (ServiceNow, SharePoint, Confluence, Google Drive, Zendesk, Jira) |

---

## 4. Tech Stack

### Full dependency matrix

| Layer | Library | Version | Used in |
|---|---|---|---|
| **LLM (primary)** | `google-genai` | ≥1.0.0 | Backend |
| **LLM (Anthropic)** | `anthropic` | ≥0.40.0 | Backend |
| **LLM (OpenAI-compat)** | `openai` | ≥1.0.0 | Backend (NVIDIA NIM, Groq, Ollama) |
| **Agent** | `langgraph` | ≥0.2.0 | Backend |
| **Agent (core)** | `langchain-core` | ≥0.3.0 | Backend |
| **MCP server** | `fastmcp` | ≥2.0.0 | Backend |
| **Observability** | `langfuse` | ≥4.0.0 | Backend |
| **Web API** | `fastapi` | ≥0.115.0 | Backend, Admin-UI |
| **ASGI server** | `uvicorn[standard]` | ≥0.30.0 | Backend, Admin-UI |
| **Rate limiting** | `slowapi` | ≥0.1.9 | Backend |
| **Async DB** | `asyncpg` | ≥0.29.0 | Backend |
| **pgvector Python** | `pgvector` | ≥0.3.0 | Backend |
| **OIDC validation** | `python-jose` | ≥3.3.0 | Backend |
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
| **Observability DB** | ClickHouse | 24.12 | Infrastructure (Langfuse) |
| **Job queue** | Redis | 7 | Infrastructure (Langfuse worker) |
| **Event storage** | MinIO | latest | Infrastructure (Langfuse S3) |
| **Identity provider** | Zitadel | 2.54.3 | Infrastructure (SSO) |

### Why these choices

| Decision | Reason |
|---|---|
| **Pluggable LLM** | Different orgs have different contracts (Gemini free tier, Anthropic enterprise, NVIDIA on-prem). One abstraction layer, zero code changes per org |
| **LangGraph** | Explicit graph structure enables conditional routing, loop detection, and `astream_events` for per-token streaming — not possible with simple chains |
| **Langfuse v3 + v4 SDK** | Full trace tree (chain → retriever → generation) with user/session attribution; ClickHouse storage handles high-volume trace writes at scale |
| **Zitadel for SSO** | Self-hostable OIDC IdP with native multi-tenancy, action hooks for custom claim enrichment, and OBO token exchange for downstream API access |
| **asyncpg** | 10-20× higher QPS than psycopg2; no ORM overhead; pgvector vectors registered as native types |
| **HNSW index** | No training phase; handles writes without rebuild; logarithmic query time; cosine ops match normalized Gemini embeddings |
| **RRF fusion** | Rank-based fusion is immune to score scale differences between BM25 and cosine similarity |
| **Jinja2 for admin** | Low-traffic internal tooling; server-rendered HTML needs no frontend build pipeline |
| **768d embeddings** | Sweet spot: Matryoshka models lose <2% recall at 768d vs 3072d; halves storage and index size |

---

## 5. Agentic RAG Pipeline

### Agent state

```python
class AgentState(TypedDict):
    messages:           list[dict]    # full conversation history (accumulating)
    query:              str           # current query (set by contextualize, may be rewritten)
    retrieved_docs:     list[dict]    # chunks from last retrieval
    grading_passed:     bool          # True when grader accepts docs
    loop_count:         int           # number of retrieve-grade iterations
    answer:             str           # final generated answer
    source_chunk_ids:   list[int]     # chunk IDs cited in the answer
    sources:            list[dict]    # [{chunk_id, doc_id, doc_title, doc_source}]
    skip_retrieval:     bool          # True for chitchat — bypass retrieval loop
    kb_overview:        bool          # True for "what's in the KB" queries
    llm_config:         dict          # per-org runtime config from app_config table
    org_id:             int | None    # org scope for retrieval and logging
    user_zitadel_token: str | None    # Zitadel access token for OBO exchange
```

### Graph edges

```
START
  └─► contextualize_node
            │
            ▼
       intent_node
            ├─ [kb_overview]  ─────────────────────────────────► kb_overview_node ──► END
            ├─ [chitchat/skip] ─────────────────────────────────► generator_node ────► END
            └─ [retrieve] ──► retriever_node
                                   └─► grader_node
                                         ├─ [RELEVANT] ─────────► generator_node ────► END
                                         └─ [IRRELEVANT]
                                               ├─ loop < max ───► rewriter_node
                                               │                        └─► retriever_node (loop)
                                               └─ loop >= max ──► clarify_node ──────► END
```

### Node descriptions

**`contextualize_node`** *(entry point)*
Uses the last 6 prior messages (3 exchanges) to rewrite ambiguous follow-ups into a fully standalone question via a lightweight LLM call. First turn: no-op, passes query through unchanged. Output becomes `state["query"]` — all downstream nodes use this field.

**`intent_node`**
Regex-based classification — no LLM call. Classifies the contextualized `state["query"]` into: retrieve (default), chitchat (greetings, thanks), or kb-overview (summarise/list document topics).

**`kb_overview_node`**
Fires when `kb_overview=True`. Fetches all document titles from the DB for the org, calls the LLM to generate a grouped topic overview, and streams the result. No vector search needed.

**`retriever_node`**
Calls `hybrid_search(query)` against PostgreSQL. Embeds the query with `text-embedding-004` (task_type=`RETRIEVAL_QUERY`) and runs the RRF SQL query. When the user has a Zitadel token, also calls the OBO ServiceNow search and merges results, deduplicating by `external_id`.

**`grader_node`**
Issues a single batched LLM call with all retrieved chunks. Uses a **conservative** prompt — a chunk must directly address the query to pass. Returns a JSON array of relevant indices. When grading fails, `retrieved_docs` is cleared so the generator cannot cite irrelevant sources.

**`rewriter_node`**
Sends the current `state["query"]` to the LLM asking for a reformulated version with different keywords. The new query replaces `state["query"]` before the next retrieval attempt. Loops until `grader_max_loops` is exhausted.

**`generator_node`**
Receives accepted chunks + injects prior conversation history (last 3 exchanges) into the prompt. Streams tokens via `adispatch_custom_event("stream_token", ...)` which are picked up by `astream_events` and forwarded as SSE events. Strictly grounded: the system prompt prohibits using general knowledge.

**`clarify_node`**
Fires when all retrieval loops exhaust without grading passing. Acknowledges the gap and asks a short clarifying question. Returns empty `source_chunk_ids` and `sources`.

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
),
fused AS (
    SELECT
        COALESCE(b.id, s.id)     AS chunk_id,
        COALESCE(b.doc_id, s.doc_id) AS doc_id,
        COALESCE(b.text, s.text) AS text,
        1.0/(60 + COALESCE(b.rank, 999)) +
        1.0/(60 + COALESCE(s.rank, 999)) AS rrf_score
    FROM bm25 b FULL OUTER JOIN semantic s ON b.id = s.id
)
SELECT f.*, d.title AS doc_title, d.source AS doc_source, d.external_id
FROM fused f JOIN documents d ON d.id = f.doc_id
WHERE ($4::bigint IS NULL OR d.org_id = $4)
ORDER BY rrf_score DESC LIMIT $3;
```

Results are deduplicated by `external_id` — the same article ingested from multiple connectors returns only the highest-scoring chunk.

---

## 6. Conversational Context

Prior to v0.3, every node treated each user message as an independent query. Follow-up questions like *"tell me more about that"* or *"what does step 2 mean?"* would retrieve irrelevant chunks because the retriever had no memory of what "that" or "step 2" referred to.

### How it works

The `contextualize_node` runs before every other node:

```python
# First message (len(messages) <= 1) — no-op
return {"query": current_query}

# Follow-up messages — rewrite with history
history = "\n".join(
    f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
    for m in messages[:-1][-6:]   # last 3 exchanges
)
prompt = f"Conversation history:\n{history}\n\nFollow-up: {current_query}\nStandalone:"
standalone = llm(prompt, system=_CONTEXTUALIZE_SYSTEM)
return {"query": standalone.strip()}
```

**System prompt:** *"Given a conversation history and a follow-up question, rewrite the follow-up as a fully standalone question that contains all necessary context. If the follow-up is already standalone, return it unchanged."*

### Examples

| User says | Contextualized query sent to retriever |
|---|---|
| *"tell me more about that"* (after discussing password reset) | *"What are the detailed steps for resetting a ServiceNow password?"* |
| *"what does step 2 say?"* | *"What is step 2 in the ServiceNow account unlock procedure?"* |
| *"How often does it sync?"* (after asking about SharePoint connector) | *"How often does the SharePoint connector sync documents?"* |
| *"Reset password"* (standalone — first turn) | *"Reset password"* (unchanged) |

### History in the generator

The generator also receives the prior conversation as a `Conversation so far:` block injected before the user question and context. This allows the LLM to naturally say *"Building on the previous answer…"* and produce responses that feel continuous rather than isolated.

---

## 7. Multi-LLM Provider Support

The platform supports three LLM providers via a unified `llm/client.py`. The active provider is set per-deployment via `LLM_PROVIDER` env var or per-org via the admin settings panel (stored in `app_config`).

### Supported providers

| Provider | `LLM_PROVIDER` value | Models | Notes |
|---|---|---|---|
| **Google Gemini** | `gemini` (default) | `gemini-2.0-flash`, `gemini-1.5-pro`, … | Embeddings always use Gemini regardless of LLM provider |
| **Anthropic Claude** | `anthropic` | `claude-3-5-sonnet-20241022`, `claude-3-haiku-20240307`, … | Requires `ANTHROPIC_API_KEY` |
| **NVIDIA NIM / OpenAI-compatible** | `nvidia` | Any model on the endpoint | Works for Groq, Ollama, Together AI, local vLLM — set `nvidia_base_url` |

### How it works

```python
# llm/client.py — generate() and stream_generate() both check provider at call time
provider = cfg.get("llm_provider") or settings.llm_provider

if provider == "anthropic":
    # uses anthropic.Anthropic().messages.create()
elif provider == "nvidia":
    # uses openai.OpenAI(base_url=nvidia_base_url).chat.completions.create()
else:
    # default: Gemini
    # uses genai.Client().models.generate_content()
```

Clients are cached per API key so rotating a key in the admin panel (which updates `app_config`) gets a fresh client on the next request without restarting the backend.

### Per-org LLM override

In the admin panel (Settings page), each org can override:

| Setting | Example |
|---|---|
| `llm_provider` | `anthropic` |
| `anthropic_model` | `claude-3-5-sonnet-20241022` |
| `anthropic_api_key` | `sk-ant-...` |
| `llm_model` | `gemini-2.0-flash` (Gemini override) |
| `nvidia_model` | `meta/llama-3.1-70b-instruct` |
| `nvidia_base_url` | `http://localhost:8080/v1` (local Ollama) |
| `nvidia_api_key` | `nvapi-...` |

---

## 8. Streaming Chat

### Backend

`POST /chat/stream` uses LangGraph's `astream_events` API. Each generator node token is dispatched as a custom event:

```python
# In generator_node
await adispatch_custom_event("stream_token", {"token": chunk}, config=config)

# In main.py /chat/stream
async for event in rag_graph.astream_events(initial_state, version="v2"):
    if event["name"] == "stream_token":
        token = event["data"]["data"]["token"]
        yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
```

The stream ends with a `done` event containing the full `sources`, `loop_count`, `session_id`, and `log_id`:

```json
{"type": "done", "sources": [...], "loop_count": 1, "session_id": "...", "log_id": 42}
```

### Frontend

The frontend connects via `fetch()` with streaming `ReadableStream` decoding. Tokens are appended to the last message in the Zustand store as they arrive. When the `done` event fires, `sources`, `logId`, and `loopCount` are merged into the message for citation and feedback display.

### Non-streaming fallback

`POST /chat` (non-streaming) is still available for API consumers and tools that do not support SSE. It returns the same response shape but waits for the full answer before responding.

---

## 9. SSO & Identity (Zitadel)

### Overview

Zitadel acts as the OIDC Identity Provider. Users authenticate via Zitadel's login UI and receive a JWT access token. The backend validates the token on every request.

### Components

| Component | Role |
|---|---|
| **Zitadel server** | OIDC IdP at `http://localhost:8088`. Manages users, orgs, and OAuth2 clients |
| **Frontend OIDC client** | `ZITADEL_FRONTEND_CLIENT_ID` — PKCE flow; no client secret in browser |
| **Backend introspection** | `ZITADEL_BACKEND_CLIENT_ID` — validates tokens via JWKS endpoint |
| **Zitadel Action** | Runs on post-auth hook; calls backend `/internal/zitadel/enrich` to inject `org_id`, `role`, `user_id` into token metadata |
| **OBO exchange** | User's Zitadel token → ServiceNow API token via `snow_token_exchange.py` |

### Auth flow

```
User → Zitadel login UI
     ← ID token + access token (JWT with org_id, role claims)
User → POST /chat/stream  (Authorization: Bearer <token>)
     → backend: validate JWT signature via JWKS
     → extract user_id, org_id, role from claims
     → org-scope retrieval; OBO exchange if Zitadel token present
```

### OBO (On-Behalf-Of) for ServiceNow

When a user's Zitadel JWT is present on a chat request, `retriever_node` checks for ServiceNow connectors with `obo_client_id` configured. If found:

1. Exchanges the user's Zitadel token for a ServiceNow API token scoped to that user's permissions
2. Runs a **live** ServiceNow KB search (respects article-level ACLs)
3. Merges live results with pgvector results, deduplicating by `external_id`

This means users who can see certain ServiceNow articles in production can find them via the chatbot — and users who cannot see them won't get them.

### Local users (password auth)

The platform also supports local password-based login via `/auth/login`. These users get a platform JWT with no Zitadel token, so OBO exchange is skipped and retrieval falls back to pgvector only.

---

## 10. Observability (Langfuse v3)

### Architecture

Langfuse v3 is a distributed trace store requiring four services:

| Service | Role |
|---|---|
| `langfuse` | Next.js web UI + API server |
| `langfuse-worker` | Async job processor (BullMQ on Redis) |
| `clickhouse` | Time-series trace storage (single-node with Keeper) |
| `redis` | BullMQ job queue between langfuse and langfuse-worker |
| `minio` | S3-compatible storage for raw event batches |

### SDK Integration (v4)

The platform uses Langfuse v4 SDK's OTEL-based API:

```python
# observability.py — singleton
lf = Langfuse(public_key=..., secret_key=..., host=...)

# main.py — top-level trace with user/session attribution
with _propagate_attributes(user_id=str(user_id), session_id=session_id, tags=[f"org:{org_id}"]):
    with lf.start_as_current_observation(name="rag-chat", as_type="chain", input={"query": ...}) as trace:
        final_state = await rag_graph.ainvoke(state)
        trace.update(output={"answer": ...})

# vector_store.py — retrieval span
with lf.start_as_current_observation(name="retrieval.hybrid_search", as_type="retriever", ...) as obs:
    obs.update(output={"num_results": len(results), "doc_titles": [...]})

# llm/client.py — generation span
with lf.start_as_current_observation(name="llm.generate", as_type="generation",
    model=model, usage_details={"input": usage_in, "output": usage_out}) as obs:
    obs.update(output=result)
```

### What you see in Langfuse

Every chat request produces a **trace tree**:

```
rag-chat (chain)                          ← top level, tagged org:N + user + session
  └── retrieval.hybrid_search (retriever) ← num_results, doc_titles
  └── llm.generate (generation)           ← model, token counts, input/output
```

Streaming requests produce the same tree with `rag-chat-stream` at the root.

### Access

| URL |
|---|---|
| `http://localhost:3000` |

Org, project, and API keys are seeded automatically on first start via `LANGFUSE_INIT_*` env vars. No manual setup needed.

---

## 11. MCP Server

The MCP server runs inside the backend process as a FastMCP application.

```bash
fastmcp dev backend/src/rag_chatbot/mcp_server/server.py
# Opens inspector UI at http://localhost:6274
```

### Tools exposed

**`hybrid_search(query: str, top_k: int = 8) → list[dict]`**
RRF hybrid search. Returns `[{chunk_id, doc_id, text, rrf_score, doc_title, doc_source}]`.

**`ingest_document(title: str, text: str, source: str = "") → dict`**
Chunks, embeds, and inserts a document. Returns `{doc_id, title, chunks}`.

**`rerank_results(docs: list[dict], query: str, top_k: int = 5) → list[dict]`**
Re-embeds each chunk and the query, returns top-K sorted by cosine similarity with `rerank_score`.

---

## 12. Database Design

All tables live in the same PostgreSQL 17 database (`rag_db`). The schema is applied idempotently on every backend startup.

### Entity-relationship overview

```
organizations
    │ 1
    │ ├──────────── N  api_keys
    │ ├──────────── N  app_config
    │ ├──────────── N  chat_logs
    │ ├──────────── N  connectors
    │ ├──────────── N  users
    └──────────── N  documents
                          │ 1
                          └── N  chunks
```

### Table definitions

#### `documents`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `title` | `TEXT` | Filename or user-provided title |
| `source` | `TEXT` | File path or URL |
| `external_id` | `TEXT` | Connector-assigned ID for deduplication (e.g. ServiceNow `sys_id`) |
| `metadata` | `JSONB` | Arbitrary key-value pairs |
| `org_id` | `BIGINT FK → organizations` | |
| `created_at` | `TIMESTAMPTZ` | |

#### `chunks`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | Referenced as `chunk_id` in API responses |
| `doc_id` | `BIGINT FK → documents` | Cascade delete |
| `chunk_index` | `INT` | Position within the parent document |
| `text` | `TEXT` | Raw chunk text |
| `embedding` | `vector(768)` | Gemini `text-embedding-004` output |
| `search_vec` | `tsvector GENERATED` | Auto-computed for BM25 |
| `created_at` | `TIMESTAMPTZ` | |

**Indexes:**

| Index | Type | Purpose |
|---|---|---|
| `idx_chunks_hnsw` | `HNSW (embedding vector_cosine_ops)` | ANN semantic search, m=16, ef_construction=64 |
| `idx_chunks_fts` | `GIN (search_vec)` | Full-text BM25 search |
| `idx_chunks_doc` | `BTREE (doc_id, chunk_index)` | Document-level chunk retrieval |

#### `organizations`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `name` | `TEXT UNIQUE` | Display name |
| `slug` | `TEXT UNIQUE` | URL-safe identifier |
| `is_active` | `BOOLEAN` | Soft-delete flag |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

#### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `email` | `TEXT UNIQUE` | |
| `password_hash` | `TEXT` | bcrypt. NULL for SSO-only users |
| `role` | `TEXT` | `superadmin`, `admin`, `user` |
| `org_id` | `BIGINT FK → organizations` | Org membership |
| `zitadel_user_id` | `TEXT` | External Zitadel subject claim (nullable) |
| `created_at` | `TIMESTAMPTZ` | |

#### `api_keys`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `org_id` | `BIGINT FK` | |
| `key_hash` | `TEXT UNIQUE` | SHA-256. Raw key never stored. |
| `label` | `TEXT` | Human-readable name |
| `is_active` | `BOOLEAN` | Revocation flag |
| `last_used` | `TIMESTAMPTZ` | Updated on each auth |
| `created_at` | `TIMESTAMPTZ` | |

#### `app_config`

Key-value runtime config, scoped per org. Overrides env defaults. Keys include `llm_provider`, `llm_model`, `anthropic_api_key`, `anthropic_model`, `nvidia_model`, `nvidia_base_url`, `nvidia_api_key`, `gemini_api_key`, `retrieval_top_k`, `grader_max_loops`, `chunk_size`, `chunk_overlap`.

Constraint: `UNIQUE (org_id, key)`.

#### `chat_logs`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | Returned as `log_id` in chat responses; used for feedback |
| `org_id` | `BIGINT FK` | |
| `session_id` | `UUID` | Groups messages in a conversation |
| `user_id` | `BIGINT FK → users` | |
| `user_message` | `TEXT` | Raw user input |
| `assistant_response` | `TEXT` | Final generated answer |
| `source_chunk_ids` | `BIGINT[]` | Chunks cited |
| `loop_count` | `INT` | Retrieval loops run |
| `latency_ms` | `INT` | Wall-clock response time |
| `feedback` | `SMALLINT` | `1` = helpful, `-1` = not helpful, `NULL` = no feedback |
| `created_at` | `TIMESTAMPTZ` | |

#### `connectors`

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PK` | |
| `org_id` | `BIGINT FK` | |
| `connector_type` | `TEXT` | `servicenow`, `sharepoint`, `confluence`, `googledrive`, `zendesk`, `jira` |
| `config` | `JSONB` | Connector-specific settings (instance URL, client ID, etc.) |
| `is_active` | `BOOLEAN` | |
| `last_synced_at` | `TIMESTAMPTZ` | |

---

## 13. API Reference

### Chat endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/chat` | JWT Bearer | Blocking chat (returns full answer) |
| `POST` | `/chat/stream` | JWT Bearer | Streaming chat (SSE, token-by-token) |
| `POST` | `/chat/feedback/{log_id}` | JWT Bearer | Submit `{value: 1}` or `{value: -1}` |
| `POST` | `/chat/followup` | JWT Bearer | Generate 3 contextual follow-up suggestions |
| `POST` | `/suggest` | JWT Bearer | Next-paragraph writing suggestion |

#### `POST /chat` and `POST /chat/stream`

```json
// Request
{
  "message": "What are the password reset steps?",
  "history": [
    {"role": "user", "content": "How do I unlock my account?"},
    {"role": "assistant", "content": "You can unlock your account by..."}
  ],
  "org_id": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}

// Response (/chat — blocking)
{
  "answer": "To reset your password, go to...",
  "source_chunk_ids": [42, 51],
  "sources": [{"chunk_id": 42, "doc_title": "Password Policy", "doc_source": "servicenow"}],
  "loop_count": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "log_id": 17
}

// Stream events (/chat/stream — SSE)
data: {"type": "token", "token": "To "}
data: {"type": "token", "token": "reset "}
...
data: {"type": "done", "sources": [...], "loop_count": 1, "session_id": "...", "log_id": 17}
```

### Auth endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | `{email, password}` → `{access_token, token_type, user}` |
| `GET` | `/auth/me` | Returns current user info from JWT |
| `POST` | `/auth/logout` | Clears session (for cookie-based flows) |

### Ingest endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest/text` | `{title, text, source?}` → `{doc_id, title, chunks}` |
| `POST` | `/ingest/file` | `multipart/form-data` with `file` field |

### Admin endpoints (`X-Admin-Key` required)

All prefixed with `/admin`.

#### Organizations
`GET /admin/orgs` · `POST /admin/orgs` · `GET /admin/orgs/{id}` · `PATCH /admin/orgs/{id}` · `DELETE /admin/orgs/{id}`

#### API Keys
`GET /admin/orgs/{id}/keys` · `POST /admin/orgs/{id}/keys` · `DELETE /admin/orgs/{id}/keys/{key_id}`

#### Documents
`GET /admin/docs` · `GET /admin/docs/{id}` · `DELETE /admin/docs/{id}` · `POST /admin/docs/ingest/text` · `POST /admin/docs/ingest/file`

#### Configuration
`GET /admin/config` · `PUT /admin/config` · `GET /admin/config/{key}`

#### Analytics
`GET /admin/analytics/summary` · `GET /admin/analytics/logs` · `GET /admin/analytics/logs/{id}` · `GET /admin/analytics/token-usage`

#### System
`GET /admin/system/health` · `POST /admin/system/schema/migrate`

---

## 14. Security Model

### Authentication layers

| Layer | Mechanism | Coverage |
|---|---|---|
| **Admin UI session** | Starlette `SessionMiddleware` (signed cookie, 8h TTL); only `superadmin` / `admin` roles admitted | All admin-ui pages |
| **Admin API** | `X-Admin-Key` header, SHA-256 hash lookup | All `/admin/**` endpoints |
| **Bootstrap** | Static `ADMIN_SECRET_KEY` env var | Before any org/key rows exist |
| **User API (local)** | JWT Bearer token from `/auth/login` | `/chat`, `/chat/stream`, `/suggest`, etc. |
| **User API (SSO)** | Zitadel JWT validated via JWKS | Same endpoints; org_id from token claims |
| **Internal Zitadel Action** | `ZITADEL_ACTION_SECRET` shared secret | `/internal/zitadel/enrich` |
| **CORS** | FastAPI `CORSMiddleware` | Prevents cross-origin chat requests |
| **Rate limiting** | slowapi per-IP, 20/min | All `/chat` and `/ingest` endpoints |

### Secrets handling

| Secret | Where stored | Never in |
|---|---|---|
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `NVIDIA_API_KEY` | Environment variable / Kubernetes Secret | Code, logs, responses |
| `DATABASE_URL` | Environment variable / Kubernetes Secret | Code, logs, responses |
| `ADMIN_SECRET_KEY` | Environment variable / Kubernetes Secret | Code, git history |
| `JWT_SECRET` | Environment variable | Code, git history |
| `ENCRYPTION_KEY` (Langfuse) | Environment variable | Code, git history |
| Raw API keys | Shown once in create-key response | Database (SHA-256 hash only) |

---

## 15. Local Development

### Prerequisites

- Docker Desktop
- Python ≥ 3.10
- Node.js 22
- A Gemini API key from [aistudio.google.com](https://aistudio.google.com)

### Step 1 — Environment file

```bash
cd rag-platform
cp .env.example .env
# Set: GEMINI_API_KEY, ADMIN_SECRET_KEY
# Optional: ANTHROPIC_API_KEY if using Anthropic provider
```

### Step 2 — Start the full stack

```bash
docker compose up --build
```

This starts: `postgres`, `backend`, `frontend`, `admin-ui`, `zitadel`, `langfuse`, `langfuse-worker`, `clickhouse`, `redis`, `minio`, `minio-init`.

First build: 3-6 minutes. Subsequent starts: ~30 seconds.

### Step 3 — Access the services

| Service | URL | Default credentials |
|---|---|---|
| Chat UI | http://localhost:5173 | alice@example.com / Alice123! |
| Admin panel | http://localhost:8080 | admin@example.com / Admin123! |
| Backend Swagger | http://localhost:8000/docs | — |
| Langfuse | http://localhost:3000 | admin@rag.local / Admin1234! |
| Zitadel | http://localhost:8088 | — |

### Step 4 — Ingest and chat

```bash
# Ingest a document
curl -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{"title": "Password Policy", "text": "To reset your password, visit the self-service portal..."}'

# Chat (non-streaming)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{"message": "How do I reset my password?", "history": []}'
```

### Step 5 — Inspect MCP tools (optional)

```bash
fastmcp dev backend/src/rag_chatbot/mcp_server/server.py
# MCP Inspector at http://localhost:6274
```

---

## 16. Docker Compose Deployment

### Service dependency graph

```
postgres ←── backend ←──┬── frontend
                        └── admin-ui

redis ←── langfuse-worker ←── langfuse ←── clickhouse
minio ←── minio-init

zitadel ←── backend (JWT validation)
```

### Starting the full stack

```bash
cp .env.example .env  # fill GEMINI_API_KEY, ADMIN_SECRET_KEY
docker compose up --build
```

### Service URLs

| Service | URL | Notes |
|---|---|---|
| Frontend (chat) | http://localhost:5173 | React SPA served by nginx |
| Admin UI | http://localhost:8080 | FastAPI + Jinja2 |
| Backend API | http://localhost:8000 | REST API + Swagger at `/docs` |
| Langfuse | http://localhost:3000 | Trace dashboard |
| Zitadel | http://localhost:8088 | OIDC IdP |
| MinIO Console | http://localhost:9001 | S3 event storage |
| PostgreSQL | localhost:5432 | `rag:rag_secret@rag_db` |

### Individual service commands

```bash
docker compose restart backend     # pick up code changes (backend mounts source)
docker compose logs -f backend     # tail logs
docker compose exec postgres psql -U rag -d rag_db   # psql shell
docker compose exec backend python -m rag_chatbot.db.connection  # re-run migrations
```

### Stopping

```bash
docker compose down         # stops containers, keeps volumes
docker compose down -v      # stops containers + deletes all volumes (full reset)
```

---

## 17. Kubernetes / Helm Deployment

Each pod has its own Helm chart under `helm/`. Langfuse, Zitadel, ClickHouse, Redis, and MinIO are expected to be deployed separately (managed services or their own Helm charts) in production.

### Chart overview

| Chart | Path | Default host |
|---|---|---|
| `rag-backend` | `helm/backend/` | `api.rag.example.com` |
| `rag-frontend` | `helm/frontend/` | `chat.rag.example.com` |
| `rag-admin-ui` | `helm/admin-ui/` | `admin.rag.example.com` |

### Deploy

```bash
# Backend
helm upgrade --install rag-backend helm/backend/ \
  --set secrets.GEMINI_API_KEY=$GEMINI_API_KEY \
  --set secrets.DATABASE_URL=$DATABASE_URL \
  --set secrets.ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY \
  --set secrets.JWT_SECRET=$JWT_SECRET \
  --set secrets.LANGFUSE_SECRET_KEY=$LANGFUSE_SECRET_KEY \
  --set ingress.host=api.rag.example.com

# Frontend
helm upgrade --install rag-frontend helm/frontend/ \
  --set ingress.host=chat.rag.example.com

# Admin UI (restricted to internal CIDR)
helm upgrade --install rag-admin helm/admin-ui/ \
  --set secrets.ADMIN_SECRET_KEY=$ADMIN_SECRET_KEY \
  --set ingress.host=admin.rag.example.com \
  --set ingress.whitelistSourceRange="10.0.0.0/8"
```

The backend chart includes an **HPA** (min 2, max 6 replicas at 70% CPU).

---

## 18. Configuration Reference

### Backend environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes (if using Gemini) | — | Google AI Studio API key |
| `ANTHROPIC_API_KEY` | If `LLM_PROVIDER=anthropic` | — | Anthropic API key |
| `DATABASE_URL` | **Yes** | — | PostgreSQL DSN |
| `ADMIN_SECRET_KEY` | No | `change-me` | Bootstrap admin key |
| `JWT_SECRET` | No | `change-me-jwt-secret` | Signs platform JWTs |
| `LLM_PROVIDER` | No | `gemini` | `gemini` / `anthropic` / `nvidia` |
| `LLM_MODEL` | No | `gemini-2.0-flash` | Gemini model |
| `ANTHROPIC_MODEL` | No | `claude-3-5-sonnet-20241022` | Anthropic model |
| `NVIDIA_MODEL` | No | — | NVIDIA NIM model name |
| `NVIDIA_BASE_URL` | No | `https://integrate.api.nvidia.com/v1` | NIM / OpenAI-compat base URL |
| `NVIDIA_API_KEY` | If `LLM_PROVIDER=nvidia` | — | |
| `EMBEDDING_MODEL` | No | `text-embedding-004` | Gemini embedding model |
| `EMBEDDING_DIM` | No | `768` | Embedding dimensions |
| `RETRIEVAL_TOP_K` | No | `8` | Chunks per hybrid search |
| `GRADER_MAX_LOOPS` | No | `3` | Max retrieve-grade iterations |
| `CHUNK_SIZE` | No | `300` | Chunk size in tokens |
| `CHUNK_OVERLAP` | No | `50` | Overlap between chunks in tokens |
| `CORS_ORIGINS` | No | `["http://localhost:5173","http://localhost:8080"]` | Allowed origins |
| `LANGFUSE_PUBLIC_KEY` | No | — | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | No | — | Langfuse project secret key (empty = disable tracing) |
| `LANGFUSE_HOST` | No | `http://langfuse:3000` | Langfuse server URL |
| `ZITADEL_ISSUER` | No | — | Zitadel OIDC issuer URL |
| `ZITADEL_BACKEND_CLIENT_ID` | No | — | Zitadel client ID for token introspection |

### Per-org runtime config (`app_config` table)

| Key | Default | Description |
|---|---|---|
| `llm_provider` | `gemini` | Provider for this org |
| `llm_model` | `gemini-2.0-flash` | Gemini model |
| `anthropic_model` | `claude-3-5-sonnet-20241022` | Anthropic model |
| `anthropic_api_key` | — | Org-specific Anthropic key |
| `nvidia_model` | — | NIM model |
| `nvidia_base_url` | — | NIM endpoint |
| `nvidia_api_key` | — | NIM key |
| `gemini_api_key` | — | Org-specific Gemini key |
| `embedding_model` | `text-embedding-004` | Embedding model |
| `embedding_dim` | `768` | Embedding dimension |
| `retrieval_top_k` | `8` | Top-K chunks |
| `grader_max_loops` | `3` | Max grader loops |
| `chunk_size` | `300` | Tokens per chunk |
| `chunk_overlap` | `50` | Overlap tokens |

### Langfuse environment variables

| Variable | Description |
|---|---|
| `LANGFUSE_INIT_ORG_ID` | Seed org ID (required to trigger init block) |
| `LANGFUSE_INIT_PROJECT_ID` | Seed project ID (required) |
| `LANGFUSE_INIT_ORG_NAME` | Display name |
| `LANGFUSE_INIT_PROJECT_NAME` | Project display name |
| `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` | Pre-seeded public key |
| `LANGFUSE_INIT_PROJECT_SECRET_KEY` | Pre-seeded secret key |
| `LANGFUSE_INIT_USER_EMAIL` | Admin user email |
| `LANGFUSE_INIT_USER_PASSWORD` | Admin user password |
| `ENCRYPTION_KEY` | 64-char hex (256-bit) key for Langfuse data encryption |
| `CLICKHOUSE_MIGRATION_URL` | ClickHouse DSN for migrations (`clickhouse://user:pass@host:9000`) |
| `CLICKHOUSE_URL` | HTTP interface (`http://host:8123`) |
| `LANGFUSE_S3_EVENT_UPLOAD_BUCKET` | MinIO bucket name |
| `LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT` | MinIO endpoint URL |
| `LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID` | MinIO access key |
| `LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY` | MinIO secret key |
| `LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE` | `"true"` for MinIO |

---

## 19. Directory Structure

```
rag-platform/
│
├── .env.example                      Root env template
├── .env                              Local secrets (git-ignored)
├── docker-compose.yml                All services + volumes (13 services)
├── clickhouse/
│   └── config.xml                    ClickHouse Keeper + cluster config (single-node)
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml                Python deps (google-genai, anthropic, openai, langfuse≥4, langgraph…)
│   └── src/rag_chatbot/
│       ├── config.py                 Pydantic Settings (all env vars)
│       ├── observability.py          Langfuse v4 singleton
│       ├── api/
│       │   ├── main.py               FastAPI app; /chat, /chat/stream, /chat/feedback, rate limits
│       │   ├── admin_router.py       Admin endpoints (orgs, docs, config, analytics, system)
│       │   ├── deps.py               require_user(), extract_zitadel_token(), X-Admin-Key check
│       │   ├── rate_limit.py         slowapi limiter config
│       │   └── zitadel_enrich.py     /internal/zitadel/enrich — Action webhook handler
│       ├── agent/
│       │   ├── state.py              AgentState TypedDict (14 fields)
│       │   ├── nodes.py              8 nodes: contextualize, intent, retriever, grader,
│       │   │                         rewriter, generator, clarify, kb_overview
│       │   └── graph.py              LangGraph StateGraph + conditional edges
│       ├── auth/
│       │   └── router.py             /auth/login, /auth/me, /auth/logout
│       ├── llm/
│       │   └── client.py             Unified multi-LLM: generate() + stream_generate()
│       │                             Supports Gemini / Anthropic / NVIDIA NIM
│       ├── mcp_server/
│       │   └── server.py             FastMCP: hybrid_search, ingest_document, rerank_results
│       ├── retrieval/
│       │   └── vector_store.py       hybrid_search() — RRF SQL, org-scoped, external_id dedup
│       ├── embeddings/
│       │   └── gemini_embedder.py    embed_text(), embed_batch()
│       ├── ingestion/
│       │   ├── loader.py             PDF / TXT / MD → raw text
│       │   ├── chunker.py            tiktoken chunking (300 tokens, 50 overlap)
│       │   └── pipeline.py           ingest_file(), ingest_text()
│       ├── connectors/
│       │   ├── sync_engine.py        APScheduler-based connector sync
│       │   ├── snow_connector.py     ServiceNow ingestion
│       │   ├── snow_token_exchange.py Zitadel → ServiceNow OBO exchange
│       │   └── …                    SharePoint, Confluence, Google Drive, Zendesk, Jira
│       └── db/
│           ├── connection.py          asyncpg pool, pgvector codec registration
│           ├── schema.sql             Base tables + indexes
│           └── migrations/
│               ├── 001_multitenancy.sql   organizations, api_keys, app_config, chat_logs
│               └── 002_users_connectors.sql  users, connectors, feedback column
│
├── frontend/
│   ├── Dockerfile                    Multi-stage: node builder → nginx
│   ├── nginx.conf                    SPA fallback
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx                   Root layout; Langfuse link in nav
│       ├── types/index.ts            ChatMessage (with logId, feedback), Org, Session
│       ├── api/client.ts             sendChat(), sendChatStream(), submitFeedback(), listOrgs()
│       ├── store/chatStore.ts        Zustand + localStorage persistence
│       ├── hooks/useChat.ts          Streaming-aware send(), loading, error
│       └── components/
│           ├── ChatWindow.tsx
│           ├── MessageBubble.tsx     Renders bubble + timestamps (Date-safe) + feedback buttons
│           ├── SourceCitations.tsx   Expandable source list with loop count
│           ├── MessageInput.tsx
│           ├── FileUpload.tsx
│           ├── OrgSelector.tsx
│           └── HistoryPanel.tsx
│
├── admin-ui/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── src/admin_ui/
│       ├── main.py
│       ├── config.py
│       ├── client.py
│       ├── routers/
│       │   ├── dashboard.py
│       │   ├── documents.py
│       │   ├── settings.py
│       │   ├── orgs.py               API keys + SSO role management
│       │   ├── analytics.py
│       │   └── connectors.py
│       └── templates/                Bootstrap 5 HTML templates
│
├── docs/
│   └── sso-obo-setup.md              Step-by-step Zitadel + OBO configuration guide
│
└── helm/
    ├── backend/                      Deployment, Service, Ingress, HPA (2-6 replicas), Secret
    ├── frontend/                     Deployment, Service, Ingress
    └── admin-ui/                     Deployment, Service, Ingress, Secret, ConfigMap
```

---

*End of document.*
