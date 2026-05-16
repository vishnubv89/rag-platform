# RAG Platform — Integration Capabilities

> **Version:** 0.3.0 · **Last updated:** May 2026
>
> This document covers how to integrate the RAG Platform with external agent ecosystems. It currently details Microsoft Copilot Studio integration via the Agent-to-Agent (A2A) protocol, and provides a reference architecture for connecting the platform as a sub-agent within a broader enterprise multi-agent system.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Microsoft Copilot Studio — A2A Integration](#2-microsoft-copilot-studio--a2a-integration)
   - 2.1 [What Is the A2A Protocol](#21-what-is-the-a2a-protocol)
   - 2.2 [Integration Architecture](#22-integration-architecture)
   - 2.3 [Gap Analysis](#23-gap-analysis)
   - 2.4 [Implementation Guide](#24-implementation-guide)
   - 2.5 [Authentication Bridging](#25-authentication-bridging)
   - 2.6 [Connecting in Copilot Studio](#26-connecting-in-copilot-studio)
   - 2.7 [What Stays Unchanged](#27-what-stays-unchanged)
3. [MCP vs A2A — When to Use Which](#3-mcp-vs-a2a--when-to-use-which)
4. [Other Integration Paths](#4-other-integration-paths)

---

## 1. Overview

The RAG Platform exposes three integration surfaces for external systems:

| Surface | Protocol | Best For |
| --- | --- | --- |
| **REST API** | HTTP/JSON | Direct API consumers, custom frontends, CI/CD pipelines |
| **MCP Server** | Model Context Protocol | Claude Desktop, LLM tool-use clients, developer tooling |
| **A2A Endpoint** *(to be implemented)* | Agent-to-Agent (A2A / JSON-RPC 2.0) | Multi-agent orchestration, Microsoft Copilot Studio, cross-platform agent delegation |

This document focuses on the A2A path, which enables the RAG Platform to operate as a **sub-agent** inside orchestrators like Microsoft Copilot Studio — receiving delegated tasks, running the full agentic RAG pipeline, and returning structured results.

---

## 2. Microsoft Copilot Studio — A2A Integration

### 2.1 What Is the A2A Protocol

The Agent-to-Agent (A2A) protocol is an open standard for agent interoperability. It defines a JSON-RPC 2.0 message envelope that allows an orchestrator (e.g., a Copilot Studio agent) to delegate tasks to a sub-agent (e.g., this RAG Platform), receive structured responses, and optionally stream results token-by-token.

Microsoft Copilot Studio's A2A support became generally available in April 2026, enabling first-, second-, and third-party agents to participate in a common orchestration fabric without vendor lock-in.

**A2A vs plain HTTP connector:**

| Concern | Plain HTTP / REST connector | A2A |
| --- | --- | --- |
| Contract | Custom per-API | Standardised JSON-RPC 2.0 |
| Discovery | Manual config | Auto-discovered via Agent Card |
| Delegation semantics | "Call an API" | "Delegate a task to another agent" |
| Multi-turn support | Manual | Built into protocol |
| Streaming | Requires custom SSE handling | Native via `tasks/sendSubscribe` |
| Rich metadata | Not standardised | Task ID, skill routing, auth context |

### 2.2 Integration Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Microsoft Copilot Studio                    │
│                                                              │
│   User → Copilot Studio Orchestrator Agent                   │
│               │  (A2A delegation)                            │
│               ▼                                              │
│        A2A Client (built into Copilot Studio)                │
└──────────────────────┬───────────────────────────────────────┘
                       │  HTTPS · JSON-RPC 2.0
                       │  POST /  (tasks/send or tasks/sendSubscribe)
                       │  GET  /.well-known/agent.json
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    RAG Platform Backend                       │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  NEW: A2A Adapter Layer  (api/a2a_router.py)        │    │
│  │                                                     │    │
│  │  GET  /.well-known/agent.json  → Agent Card         │    │
│  │  POST /                        → JSON-RPC handler   │    │
│  │    tasks/send       → blocking response             │    │
│  │    tasks/sendSubscribe → SSE streaming              │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │  delegates to existing pipeline    │
│                         ▼                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Existing LangGraph Agent (agent/graph.py)          │    │
│  │                                                     │    │
│  │  contextualize → intent → retriever → grader        │    │
│  │    → rewriter (loop) → generator / clarify          │    │
│  └─────────────────────────────────────────────────────┘    │
│                         │                                    │
│              ┌──────────┴──────────┐                        │
│              ▼                     ▼                        │
│     PostgreSQL + pgvector     Langfuse traces               │
└──────────────────────────────────────────────────────────────┘
```

**Request lifecycle for a delegated task:**

```
Copilot Studio sends:
  POST /
  {
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "id": "<rpc-id>",
    "params": {
      "task": {
        "id": "<task-uuid>",
        "message": {
          "role": "user",
          "parts": [{ "text": "What is the password reset policy?" }]
        }
      }
    }
  }

RAG Platform:
  1. A2A adapter unwraps the task message
  2. Calls LangGraph pipeline (contextualize → retrieve → grade → generate)
  3. Wraps answer + sources into A2A TaskResult / Artifact
  4. Returns JSON-RPC 2.0 response

Copilot Studio receives:
  {
    "jsonrpc": "2.0",
    "id": "<rpc-id>",
    "result": {
      "id": "<task-uuid>",
      "status": { "state": "completed" },
      "artifacts": [{
        "parts": [{ "text": "To reset your password, visit the self-service portal..." }],
        "metadata": {
          "sources": [{ "doc_title": "Password Policy", "doc_source": "servicenow" }],
          "loop_count": 1
        }
      }]
    }
  }
```

### 2.3 Gap Analysis

The following table maps what Copilot Studio requires against the current state of the RAG Platform:

| Requirement | Current State | Gap | Effort |
| --- | --- | --- | --- |
| **Agent Card** at `/.well-known/agent.json` | Not present | Must add `GET /.well-known/agent.json` endpoint returning capability metadata | Low (~30 min) |
| **JSON-RPC 2.0 task endpoint** (`POST /`) | Not present | Must add A2A adapter that unwraps `tasks/send`, calls LangGraph, wraps response | Medium (1–2 days) |
| **SSE streaming** in A2A format (`tasks/sendSubscribe`) | Present in `/chat/stream` but in custom SSE format | Must wire existing `stream_token` events into A2A streaming envelope | Medium (0.5–1 day) |
| **Auth bridging** for Copilot Studio | JWT Bearer + API keys exist | Must expose an org-scoped API key or OAuth2 client credentials Copilot Studio can use | Low (~2 hrs) |
| **HTTPS public endpoint** | Configured in Helm Ingress | No code change; deployment concern only | Minimal |
| **Existing LangGraph pipeline** | Fully implemented | No changes required | — |
| **Existing SSE token streaming** | Fully implemented | Reused as-is behind the adapter | — |
| **Database, connectors, observability** | Fully implemented | No changes required | — |

**Nothing in the existing codebase needs to be replaced.** The A2A adapter is a pure addition — a new router mounted alongside the existing FastAPI app.

### 2.4 Implementation Guide

#### Step 1 — Install the A2A Python SDK

```bash
pip install a2a-sdk
```

Add to `backend/pyproject.toml`:

```toml
[project.dependencies]
a2a-sdk = ">=1.0.0"
```

The SDK provides a FastAPI-compatible application that handles JSON-RPC routing, SSE streaming, and Agent Card serving. It can mount its routes directly onto an existing FastAPI app via `add_routes_to_app()` without replacing anything.

---

#### Step 2 — Define the Agent Card

Create `backend/src/rag_chatbot/api/a2a_router.py`:

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from rag_chatbot.config import settings

def get_agent_card() -> dict:
    return {
        "name": "RAG Knowledge Assistant",
        "description": (
            "Agentic RAG platform with hybrid BM25 + vector search over "
            "organisational knowledge bases. Supports follow-up questions, "
            "source citations, and multi-connector ingestion."
        ),
        "version": "0.3.0",
        "url": settings.public_base_url,          # e.g. https://api.rag.example.com
        "documentationUrl": f"{settings.public_base_url}/docs",
        "provider": {
            "organization": "Your Organisation",
            "url": settings.public_base_url
        },
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        "authentication": {
            "schemes": ["bearer"]
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "rag_query",
                "name": "Knowledge Base Query",
                "description": (
                    "Answers questions by retrieving and grading relevant chunks "
                    "from the organisational knowledge base using hybrid search. "
                    "Handles follow-up questions, rewrites queries on retrieval "
                    "failure, and returns grounded answers with source citations."
                ),
                "tags": ["rag", "search", "knowledge-base"],
                "examples": [
                    "What is the password reset policy?",
                    "How do I raise a ServiceNow incident?",
                    "What's in the knowledge base?"
                ]
            }
        ]
    }
```

Register it in `main.py`:

```python
from rag_chatbot.api.a2a_router import get_agent_card

@app.get("/.well-known/agent.json", include_in_schema=False)
async def agent_card():
    return JSONResponse(content=get_agent_card())
```

---

#### Step 3 — Implement the JSON-RPC Task Handler

Add to `a2a_router.py`:

```python
import uuid
from fastapi import Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from rag_chatbot.api.deps import require_user
from rag_chatbot.agent.graph import rag_graph
import json

async def _run_rag(user_text: str, org_id: int, session_id: str) -> dict:
    """Delegates to the existing LangGraph pipeline."""
    state = {
        "messages": [{"role": "user", "content": user_text}],
        "query": user_text,
        "org_id": org_id,
        "loop_count": 0,
        "skip_retrieval": False,
        "kb_overview": False,
        "grading_passed": False,
        "retrieved_docs": [],
        "answer": "",
        "source_chunk_ids": [],
        "sources": [],
        "llm_config": {},
        "user_zitadel_token": None,
    }
    return await rag_graph.ainvoke(state)


def _wrap_artifact(result: dict, task_id: str) -> dict:
    """Wraps LangGraph output into an A2A TaskResult."""
    return {
        "id": task_id,
        "status": {"state": "completed"},
        "artifacts": [
            {
                "parts": [{"text": result.get("answer", "")}],
                "metadata": {
                    "sources": result.get("sources", []),
                    "loop_count": result.get("loop_count", 0),
                    "source_chunk_ids": result.get("source_chunk_ids", []),
                },
            }
        ],
    }


async def _stream_rag(user_text: str, org_id: int, task_id: str):
    """Yields A2A-formatted SSE events wrapping existing stream_token events."""
    state = {
        "messages": [{"role": "user", "content": user_text}],
        "query": user_text,
        "org_id": org_id,
        "loop_count": 0,
        "skip_retrieval": False,
        "kb_overview": False,
        "grading_passed": False,
        "retrieved_docs": [],
        "answer": "",
        "source_chunk_ids": [],
        "sources": [],
        "llm_config": {},
        "user_zitadel_token": None,
    }
    async for event in rag_graph.astream_events(state, version="v2"):
        if event["name"] == "stream_token":
            token = event["data"]["data"]["token"]
            payload = {
                "jsonrpc": "2.0",
                "method": "tasks/update",
                "params": {
                    "task": {
                        "id": task_id,
                        "status": {"state": "working"},
                        "artifacts": [{"parts": [{"text": token}]}],
                    }
                },
            }
            yield f"data: {json.dumps(payload)}\n\n"

    # Final done event
    done = {
        "jsonrpc": "2.0",
        "method": "tasks/update",
        "params": {
            "task": {"id": task_id, "status": {"state": "completed"}}
        },
    }
    yield f"data: {json.dumps(done)}\n\n"


async def handle_a2a_request(request: Request, user=Depends(require_user)):
    body = await request.json()
    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})
    task = params.get("task", {})
    task_id = task.get("id", str(uuid.uuid4()))
    parts = task.get("message", {}).get("parts", [])
    user_text = next((p["text"] for p in parts if "text" in p), "")
    org_id = user.get("org_id")

    if method == "tasks/send":
        result = await _run_rag(user_text, org_id, task_id)
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": _wrap_artifact(result, task_id),
        })

    elif method == "tasks/sendSubscribe":
        return StreamingResponse(
            _stream_rag(user_text, org_id, task_id),
            media_type="text/event-stream",
        )

    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }, status_code=400)
```

Register the handler in `main.py`:

```python
from rag_chatbot.api.a2a_router import handle_a2a_request

# Mount A2A JSON-RPC endpoint — must be POST on root or a dedicated path
app.add_api_route(
    "/a2a",
    handle_a2a_request,
    methods=["POST"],
    dependencies=[Depends(require_user)],
    include_in_schema=False,
)
```

> **Note:** Update the Agent Card's `url` field to point to `https://api.rag.example.com/a2a` if you mount on `/a2a` rather than `/`.

---

#### Step 4 — Add `public_base_url` to Settings

In `config.py`, add:

```python
class Settings(BaseSettings):
    ...
    public_base_url: str = "https://api.rag.example.com"
```

And in `.env` / Helm secrets:

```
PUBLIC_BASE_URL=https://api.rag.example.com
```

---

#### Step 5 — Verify the Agent Card Is Reachable

```bash
curl https://api.rag.example.com/.well-known/agent.json
```

Expected response:

```json
{
  "name": "RAG Knowledge Assistant",
  "version": "0.3.0",
  "capabilities": { "streaming": true },
  "skills": [{ "id": "rag_query", ... }]
}
```

Copilot Studio fetches this URL automatically when you enter the endpoint and uses it to populate the agent's name and description in the UI.

---

#### Step 6 — Test the Task Endpoint Directly

```bash
# Blocking (tasks/send)
curl -X POST https://api.rag.example.com/a2a \
  -H "Authorization: Bearer <org-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "id": "test-1",
    "params": {
      "task": {
        "id": "task-abc",
        "message": {
          "role": "user",
          "parts": [{ "text": "What is the password reset policy?" }]
        }
      }
    }
  }'

# Streaming (tasks/sendSubscribe)
curl -N -X POST https://api.rag.example.com/a2a \
  -H "Authorization: Bearer <org-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/sendSubscribe",
    "id": "test-2",
    "params": { "task": { "id": "task-xyz", "message": { "role": "user", "parts": [{ "text": "How do I raise a ServiceNow incident?" }] } } }
  }'
```

### 2.5 Authentication Bridging

Copilot Studio sends an `Authorization: Bearer <token>` header with every A2A request. The RAG Platform's existing `require_user()` dependency (in `api/deps.py`) already validates bearer tokens via both JWT and hashed API key lookup — no changes needed there.

**Recommended setup for Copilot Studio connections:**

| Option | How | Use When |
| --- | --- | --- |
| **Org-scoped API key** | Create a dedicated API key in the admin panel for the Copilot Studio connection; enter it as the bearer token in the Copilot Studio connection config | Simplest; suitable for org-bound integrations |
| **OAuth2 client credentials** | Configure a Zitadel machine user / service account and use its access token | Required when you need Zitadel RBAC enforcement on delegated tasks |
| **OBO (user-scoped)** | Pass the end-user's Zitadel token through Copilot Studio's connection context | Enables per-user ServiceNow ACL enforcement on live KB searches |

For most deployments, start with the org-scoped API key. The admin panel (Org Detail page → API Keys) lets you create and label a key specifically for Copilot Studio.

### 2.6 Connecting in Copilot Studio

Once the A2A endpoint is live and the Agent Card is reachable:

1. Open **Copilot Studio** and navigate to your orchestrator agent.
2. Select **Agents → Add an agent → Connect to an external agent → Agent2Agent**.
3. Enter the endpoint URL: `https://api.rag.example.com/a2a`
4. Copilot Studio will auto-fetch `/.well-known/agent.json` and populate the name and description.
5. Select or create a **connection** — choose bearer token and paste in the org API key.
6. Select **Add and configure**.
7. In the orchestrator agent's instructions, describe when to delegate to the RAG sub-agent, e.g.:
   > *"When the user asks a question about internal policies, procedures, or knowledge base articles, delegate the task to the RAG Knowledge Assistant agent."*

**Validation:** Send a natural language query from the Copilot Studio test pane that should trigger delegation. Confirm the response originates from the RAG pipeline (sources will be present in the artifact metadata).

### 2.7 What Stays Unchanged

The following parts of the RAG Platform require **zero modifications** for A2A integration:

| Component | Reason |
| --- | --- |
| `agent/graph.py` — LangGraph StateGraph | A2A adapter calls `rag_graph.ainvoke()` / `rag_graph.astream_events()` directly |
| `agent/nodes.py` — all 8 nodes | Untouched; pipeline logic is identical regardless of caller |
| `retrieval/vector_store.py` — hybrid search | Called by `retriever_node` as normal |
| `api/main.py` — existing `/chat`, `/chat/stream` | Existing endpoints remain live; A2A is an additive mount |
| `mcp_server/server.py` — MCP tools | MCP and A2A serve different clients; both run concurrently |
| `observability.py` — Langfuse tracing | A2A-originated requests produce identical trace trees |
| Database, connectors, Zitadel, Ingress | No changes |

---

## 3. MCP vs A2A — When to Use Which

Both MCP and A2A are already partially supported by the RAG Platform. They serve different integration scenarios:

| Scenario | Use | Why |
| --- | --- | --- |
| Claude Desktop or LLM tool-use clients calling `hybrid_search` | **MCP** | MCP is the tool-invocation protocol for LLM clients; already implemented via FastMCP |
| Copilot Studio delegating a full user query to the RAG agent | **A2A** | A2A is designed for agent-to-agent task delegation with richer context and multi-turn support |
| A developer testing retrieval during local development | **MCP** | MCP Inspector at `localhost:6274` provides an interactive UI |
| A Copilot Studio agent routing between multiple specialist agents | **A2A** | A2A lets the orchestrator pick the right sub-agent based on skill metadata |
| A custom app wanting direct REST access | **REST API** | Existing `/chat` and `/ingest` endpoints |

MCP and A2A can and should coexist. They are complementary, not alternatives.

---

## 4. Other Integration Paths

The following integration patterns are possible using the existing REST API without any additional protocol work:

| Integration | Mechanism | Entry Point |
| --- | --- | --- |
| **Custom chat frontend** | `POST /chat/stream` (SSE) + JWT auth | `api/main.py` |
| **CI/CD doc ingestion** | `POST /ingest/text` or `POST /ingest/file` with API key | `api/main.py` |
| **Analytics export** | `GET /admin/analytics/logs` with admin key | `api/admin_router.py` |
| **Custom connector** | Implement the connector interface in `connectors/`; register in `connectors` table | `connectors/sync_engine.py` |
| **Slack / Teams bot** | POST to `/chat` from a bot handler; stream responses via webhook | `api/main.py` |
| **ServiceNow Virtual Agent** | Call `/chat` as an outbound REST integration from ServiceNow | `api/main.py` |

For integrations that require agent-level reasoning and context propagation (rather than simple API calls), the A2A path described in Section 2 is recommended.

---

*End of document.*
