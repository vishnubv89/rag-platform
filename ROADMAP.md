# RAG Platform — Improvement Roadmap

> **Coding principles applied throughout every phase:**
> - Simplicity first — smallest change that works
> - Surgical edits — touch only what's needed
> - Verify before claiming done — build + test after each phase
> - Branch per phase: `feat/phase-N-<name>`

---

## Completed

| What | When |
|---|---|
| Multi-tenant org isolation + admin panel | Phase 1–3 |
| Google Drive, Zendesk, Jira connectors | Phase 5 |
| Admin session auth + cookie-based org scope | Session 2 |
| Embedding batch bug fix | Session 2 |
| Chunk preview in document detail | Session 2 |
| Conversational tone (no "based on provided document chunks") | Session 2 |
| Follow-up suggestion chips after each response | Session 2 |
| Knowledge grounding — strict grader + clarify node | Session 3 |
| **Streaming — token-by-token SSE via astream_events** | Session 3 |
| **Feedback loop** — thumbs up/down, `log_id` in SSE done, feedback ratio in admin analytics | PR #9 |
| **Conversational context** — `contextualize_node` rewrites follow-ups as standalone queries | PR #9 |
| **Zitadel SSO** — OIDC PKCE login, JWT validation, org/role claims, Zitadel Action enrichment | PR #9 |
| **OBO token exchange** — Zitadel → ServiceNow user-scoped API token; live KB search in retriever | PR #9 |
| **Multi-LLM support** — Gemini, Anthropic Claude, NVIDIA NIM / OpenAI-compatible endpoints | PR #9 |
| **MCP server** — `hybrid_search`, `ingest_document`, `rerank_results` tools via FastMCP | PR #9 |
| **rerank_results MCP tool** — cosine re-ranking over retrieved chunks | PR #9 |
| **A2A endpoint** — JSON-RPC 2.0 agent-to-agent protocol; Copilot Studio compatible | PR #10 |
| **Action routing** — `intent_node` detects action commands; `action_node` calls live APIs, bypassing RAG | PR #10 |
| **ServiceNow actions** — create incident (P1–P4), resolve/close by number or conversation reference, create change requests | PR #10 / #11 |
| **Jira actions** — create issue, triage/transition by key | PR #10 |
| **Slack / Teams notification dispatch** — natural-language "post to #channel" routed to Slack SDK / Teams webhook | PR #10 |
| **ABAC** — `document_labels` + `user_attributes` tables; enforced in RRF SQL at query time; no post-filter | PR #10 |
| **DLP pre-ingestion** — regex rules block API keys, SSNs, credit cards; optional Nightfall API | PR #10 |
| **Slack / Teams / Workday / Azure AD / Okta connectors** — knowledge sync + identity sync | PR #10 |
| **Datadog APM + OpenTelemetry** — `init_datadog()`, `init_otel()` in lifespan; opt-in via env vars | PR #10 |
| **Dashboards tab** — Power BI / Looker iframe embed (`BIEmbed`); reads `VITE_POWERBI_EMBED_URL` / `VITE_LOOKER_EMBED_URL` | PR #11 |
| **nginx DNS re-resolution** — `resolver 127.0.0.11 valid=10s` prevents stale upstream IP after restarts | PR #11 |
| **restart policies** — `restart: unless-stopped` on all services; eliminates cascade outage when postgres exits | PR #11 |
| **Lint cleanup** — `useWizardCheck` extracted to hook; KnowledgeHub setState-in-effect fixed; ruff E402 fixed | PR #11 |

---

## Phase 7 — Server-side Session History
**Branch:** `feat/phase7-sessions`
**Effort:** ~1 day
**Why:** localStorage sessions disappear on browser clear / device switch. Data is already in `chat_logs` — just needs a read API and frontend wiring.

### What
- `GET /chat/sessions` — list distinct sessions for current user (preview text, timestamp, message count)
- `GET /chat/sessions/{session_id}` — return all messages in a session (reconstruct from chat_logs)
- `HistoryPanel` reads from API on mount; localStorage used as write-through cache for current session

### Files
| File | Change |
|---|---|
| `api/main.py` | GET /chat/sessions, GET /chat/sessions/{session_id} |
| `api/client.ts` | listSessions(), getSession(id) |
| `store/chatStore.ts` | loadSessionsFromApi() action |
| `components/Sidebar.tsx` | Fetch sessions on mount; click restores messages |

---

## Phase 8 — Semantic Chunking
**Branch:** `feat/phase8-chunking`
**Effort:** ~1 day
**Why:** Fixed-size tiktoken chunking splits mid-sentence and mid-paragraph. Semantic chunking (paragraph + heading boundaries) significantly improves retrieval quality — chunks map to coherent ideas, not arbitrary token windows.

### What
- Replace `TokenChunker` with `SemanticChunker` — split on `\n\n` and heading markers (`#`), then guard size with tiktoken (merge small, split oversized)
- Keep same function signature — zero changes to ingestion pipeline
- Existing chunks unaffected; re-ingest docs to get better chunks

### Strategy
```
Split on paragraph boundaries (\n\n)
→ Merge consecutive short paragraphs until approaching chunk_size tokens
→ Split oversized paragraphs at sentence boundaries (". ", "? ", "! ")
→ Add configurable overlap by repeating last N tokens of previous chunk
```

### Files
| File | Change |
|---|---|
| `ingestion/chunker.py` | New SemanticChunker; keep TokenChunker for backwards compat |
| `ingestion/pipeline.py` | Switch to SemanticChunker |
| `config.py` | Add `chunker_strategy: str = "semantic"` setting |

---

## Phase 9 — Codebase Cleanup
**Branch:** `feat/phase9-cleanup`
**Effort:** ~half day
**Why:** Loose ends from rapid iteration.

### What
- **Wire token usage** — populate `prompt_tokens` / `completion_tokens` in `chat_logs` from Gemini/Anthropic response metadata (low effort, unlocks cost analytics in admin)
- **`/suggest` endpoint** — build out a proper writing-assistant UI surface, or cut it
- **Action connector config** — surface Slack/Teams/ServiceNow/Jira connector config in the admin UI (currently env-var only)
- **ABAC admin UI** — add `document_labels` management to the admin panel (currently API-only)

---

## Phase 10 — ragkit Extraction (Parked)
See `RAGKIT.md`. Revisit after Phase 9 completes and the platform is stable.

---

## Sequence Summary

```
Phase 7: Session history      ← next
Phase 8: Semantic chunking
Phase 9: Cleanup + polish
Phase 10: ragkit              ← after platform stabilises
```
