# ragkit — Idea Doc

> **Status:** Parked — revisit when RAG platform v0.2 stabilises
> **Last updated:** May 2026

---

## The Idea

Extract the reusable core of the RAG platform into a standalone Python library called **ragkit** — published to PyPI, optionally also exposed as an MCP server.

Not a framework. Not a platform. A **toolkit of independent, composable components** for building RAG products on PostgreSQL.

The RAG platform itself becomes the reference implementation — the production product built on top of ragkit. This proves the separation is clean and gives developers a real-world example to learn from.

---

## The Pitch

> "If you use PostgreSQL, here's the best RAG stack for it."

LangChain and LlamaIndex abstract over 20+ vector databases. ragkit doesn't. It bets entirely on PostgreSQL + pgvector — one database, no extra infrastructure, RRF hybrid search in a single SQL query. The opinionated PostgreSQL bet is the differentiator.

| Dimension | LangChain / LlamaIndex | ragkit |
|---|---|---|
| Vector DB | Abstracted over 20+ | PostgreSQL only — no config, just works |
| Retrieval | Pluggable, complex | RRF hybrid search, one SQL query |
| Grounding | Not built in | Conservative grader + clarify node as first-class |
| Dependencies | Massive | Thin — asyncpg, google-genai, langgraph, tiktoken |
| Learning curve | High | Low — functions and classes, not a framework |

---

## Modules to Extract

Sourced from `backend/src/rag_chatbot/` in the current platform.

### Drop-in (zero changes needed today)

| Current file | ragkit module | What it does |
|---|---|---|
| `retrieval/vector_store.py` | `ragkit.retrieval.HybridSearch` | RRF BM25 + cosine search in PostgreSQL |
| `embeddings/gemini_embedder.py` | `ragkit.embeddings.GeminiEmbedder` | Per-text Gemini embedding with retry/backoff |
| `ingestion/chunker.py` | `ragkit.ingestion.TokenChunker` | tiktoken chunking, configurable size + overlap |
| `ingestion/loader.py` | `ragkit.ingestion.FileLoader` | PDF / TXT / MD → raw text |
| `ingestion/pipeline.py` | `ragkit.ingestion.IngestPipeline` | Composes loader → chunker → embedder → DB |
| `api/rate_limit.py` | `ragkit.api.RateLimiter` | slowapi wrapper for FastAPI |

### Reusable with light adaptation

| Current file | ragkit module | What changes |
|---|---|---|
| `agent/nodes.py` | `ragkit.agent.nodes` | Decouple from settings import; accept config as args |
| `agent/graph.py` | `ragkit.agent.build_rag_graph()` | Factory function, accept custom nodes |
| `agent/state.py` | `ragkit.agent.AgentState` | No changes needed |
| `db/connection.py` | `ragkit.db.create_pool()` | Remove settings import; accept db_url as param |
| `db/schema.sql` | `ragkit.db.apply_schema()` | Wrap in a Python runner function |
| `connectors/sync_engine.py` | `ragkit.connectors.SyncScheduler` | Accept connector list as arg |
| `api/deps.py` | `ragkit.api.ApiKeyAuth` | Accept table name as param |

---

## Proposed Package Structure

```
ragkit/
├── embeddings/
│   ├── base.py          # BaseEmbedder ABC
│   └── gemini.py        # GeminiEmbedder
│
├── retrieval/
│   ├── base.py          # BaseRetriever ABC
│   └── hybrid.py        # HybridSearch (RRF SQL)
│
├── ingestion/
│   ├── loader.py        # FileLoader
│   ├── chunker.py       # TokenChunker
│   └── pipeline.py      # IngestPipeline
│
├── agent/
│   ├── state.py         # AgentState TypedDict
│   ├── nodes.py         # grader, rewriter, clarify, generator
│   └── graph.py         # build_rag_graph()
│
├── db/
│   ├── pool.py          # create_pool() + pgvector codec
│   └── schema.py        # apply_schema()
│
└── connectors/
    ├── base.py          # BaseConnector ABC
    └── scheduler.py     # SyncScheduler
```

---

## Distribution

**Phase 1 — PyPI package**
Standard `pip install ragkit`. Optional dependency groups so users only install what they need:

```toml
[project.optional-dependencies]
gemini = ["google-genai>=1.0.0"]
mcp    = ["fastmcp>=2.0.0"]
full   = ["ragkit[gemini,mcp]"]
```

**Phase 2 — MCP server**
Publish `hybrid_search`, `ingest_document`, `grade_chunks` as MCP tools. Any MCP client (Claude Desktop, other LangGraph agents, external services) can call them without writing Python. The FastMCP server in the platform is already 80% of this.

**Phase 3 — Both surfaces**
PyPI for developers building Python services. MCP for agent-to-agent tool use. Same underlying code, two distribution surfaces.

---

## Minimal Working Example (target API)

```python
from ragkit.embeddings import GeminiEmbedder
from ragkit.retrieval import HybridSearch
from ragkit.ingestion import IngestPipeline

embedder = GeminiEmbedder(api_key="...")
db_url   = "postgresql://user:pass@localhost/mydb"

# Ingest
pipeline = IngestPipeline(embedder=embedder, db_url=db_url)
await pipeline.ingest_file("report.pdf", title="Q4 Report", org_id=1)

# Search
search = HybridSearch(db_url=db_url)
chunks = await search.query("what were the Q4 results?", top_k=5, org_id=1)

# Full agentic loop
from ragkit.agent import build_rag_graph

graph = build_rag_graph(embedder=embedder, db_url=db_url)
result = await graph.ainvoke({"query": "what were the Q4 results?", "messages": []})
print(result["answer"])
```

---

## What Needs to Change Before Extraction

1. **Remove global settings imports** — Every module currently imports from `rag_chatbot.config`. Needs to accept config as constructor arguments.

2. **Add ABCs** — `BaseEmbedder`, `BaseRetriever`, `BaseConnector` so users can swap implementations. Gemini becomes the default, not the only option.

3. **Docstrings on public functions** — Type hints are already there. One-line descriptions unlock auto-generated API docs via `mkdocstrings`.

4. **Docs site** — `mkdocs-material` + `mkdocstrings` auto-generates an API reference from type hints. Add a Getting Started page and it's shippable.

5. **Separate repo** — `ragkit` gets its own repo. The RAG platform's `pyproject.toml` adds `ragkit` as a dependency. Platform becomes the reference implementation.

---

## Estimated Effort to Ship v0.1

| Task | Effort |
|---|---|
| Extract 4 core modules (embedder, search, chunker, pipeline) | 1 day |
| Replace settings imports with constructor args | half day |
| Add BaseEmbedder + BaseRetriever ABCs | half day |
| Write docstrings | half day |
| Set up mkdocs-material site | half day |
| PyPI publish + CI | half day |
| **Total** | **~3 days** |

Agent modules and MCP surface → v0.2.

---

## Open Questions for When We Revisit

- Name: `ragkit` / `pg-rag` / `ragcore` / something else?
- Licence: MIT (same as platform) or Apache 2.0?
- Should the schema (documents/chunks tables) be part of ragkit or left to the user?
- Do we want a CLI (`ragkit ingest report.pdf`) alongside the Python API?
- Versioning: tie to the platform version or independent semver?

---

*Revisit after RAG platform v0.2 stabilises and connectors are production-tested.*
