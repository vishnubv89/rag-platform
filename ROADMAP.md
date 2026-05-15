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
| Embedding batch bug fix (SDK returns 1 vector for N texts) | Session 2 |
| Chunk preview in document detail | Session 2 |
| Conversational tone (no "based on provided document chunks") | Session 2 |
| Follow-up suggestion chips after each response | Session 2 |
| Knowledge grounding — strict grader + clarify node | Session 3 |
| **Streaming — token-by-token SSE via astream_events** | Session 3 |

---

## Phase 6 — Feedback Loop
**Branch:** `feat/phase6-feedback`
**Effort:** ~1 day
**Why first:** Highest signal value. Without this you can't measure whether any other improvement actually worked.

### What
- `feedback` SMALLINT column in `chat_logs` (1 = up, -1 = down, NULL = none)
- `POST /chat/{log_id}/feedback` — users submit thumbs up/down
- `log_id` returned in SSE `done` event and stored on `ChatMessage`
- Thumbs up/down buttons in `MessageBubble` (assistant messages only)
- Feedback ratio shown in admin analytics dashboard

### Files
| File | Change |
|---|---|
| `db/migrations/002_feedback.sql` | ADD COLUMN feedback SMALLINT |
| `api/main.py` | POST /chat/{log_id}/feedback endpoint; return log_id in stream done event |
| `types/index.ts` | Add logId to ChatMessage; add to StreamEvent done |
| `api/client.ts` | submitFeedback(logId, value) |
| `hooks/useChat.ts` | Store log_id from done event on message |
| `components/MessageBubble.tsx` | Thumbs up/down buttons, disabled after voted |
| `admin_router.py` | Feedback ratio in analytics summary |

---

## Phase 7 — Server-side Session History
**Branch:** `feat/phase7-sessions`
**Effort:** ~1.5 days
**Why:** localStorage sessions disappear on browser clear / device switch. Data is already in `chat_logs` — just needs a read API and frontend wiring.

### What
- `GET /chat/sessions` — list distinct sessions for current user (preview text, timestamp, message count)
- `GET /chat/sessions/{session_id}` — return all messages in a session (reconstruct from chat_logs)
- `HistoryPanel` reads from API instead of localStorage on mount
- Keep localStorage as write-through cache for current session

### Files
| File | Change |
|---|---|
| `api/main.py` | GET /chat/sessions, GET /chat/sessions/{session_id} |
| `api/client.ts` | listSessions(), getSession(id) |
| `store/chatStore.ts` | loadSessionsFromApi() action |
| `components/HistoryPanel.tsx` | Fetch sessions on mount; click restores messages |

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
**Why:** Dead code adds cognitive load and maintenance surface without delivering value.

### What
- **Remove** `rerank_results` MCP tool — defined, never called by the agent
- **Remove** `prompt_tokens` / `completion_tokens` columns from `chat_logs` (reserved, never populated) — OR wire them up to Gemini usage metadata
- **Remove or graduate** `/suggest` writing-assistant endpoint — either build it out properly (own UI surface) or cut it

### Decision needed before Phase 9
- Wire token usage from Gemini response → populate columns (low effort, useful for cost analytics)
- `/suggest` — keep if there's a plan to surface it, cut if not

---

## Phase 10 — Document-level Permissions (Deferred)
**Branch:** `feat/phase10-permissions`
**Effort:** ~1 week
**Why deferred:** Requires mirroring ACLs from 6 different connector systems. High complexity, only needed when a real customer blocks on it.

### What
- `doc_permissions` table: `(doc_id, org_id, allowed_users[], allowed_groups[])`
- Connector sync populates permissions alongside content
- `hybrid_search()` filters by caller's identity
- Requires JWT claims to carry group memberships

---

## Phase 11 — ragkit Extraction (Parked)
See `RAGKIT.md`. Revisit after Phase 9 completes and the platform is stable.

---

## Sequence Summary

```
Phase 6: Feedback loop      ← start now
Phase 7: Session history
Phase 8: Semantic chunking
Phase 9: Cleanup
Phase 10: Permissions       ← when a customer needs it
Phase 11: ragkit            ← after platform stabilises
```
