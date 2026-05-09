from contextlib import asynccontextmanager
import json
from pathlib import Path
import tempfile
import time
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rag_chatbot.api.rate_limit import limiter, rate_limit_exceeded_handler
from pydantic import BaseModel

from rag_chatbot.config import settings
from rag_chatbot.db.connection import run_schema, close_pool, get_pool
from rag_chatbot.agent.graph import rag_graph
from rag_chatbot.ingestion.pipeline import ingest_file, ingest_text
from rag_chatbot.api.admin_router import router as admin_router
from rag_chatbot.api.deps import require_user
from rag_chatbot.auth.router import router as auth_router
from rag_chatbot.connectors.sync_engine import start_scheduler, stop_scheduler
from rag_chatbot.retrieval.vector_store import hybrid_search
from rag_chatbot.llm.client import generate as llm_generate


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_schema()
    start_scheduler()
    yield
    stop_scheduler()
    await close_pool()


app = FastAPI(
    title="Agentic RAG Chatbot",
    description="LangGraph + FastMCP + pgvector + Gemini",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    org_id: int | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    source_chunk_ids: list[int]
    sources: list[dict]
    loop_count: int
    session_id: str


class SuggestRequest(BaseModel):
    context: str
    org_id: int | None = None


class SuggestResponse(BaseModel):
    suggestion: str
    sources: list[dict]


class FollowUpRequest(BaseModel):
    messages: list[dict]
    org_id: int | None = None


class FollowUpResponse(BaseModel):
    suggestions: list[str]


class IngestTextRequest(BaseModel):
    title: str
    text: str
    source: str = ""


class IngestResponse(BaseModel):
    doc_id: int
    title: str
    chunks: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(req: ChatRequest, request: Request):
    user = await require_user(request)
    session_id = req.session_id or str(uuid4())
    messages = req.history + [{"role": "user", "content": req.message}]
    initial_state = {
        "messages": messages,
        "query": req.message,
        "retrieved_docs": [],
        "grading_passed": False,
        "loop_count": 0,
        "answer": "",
        "source_chunk_ids": [],
        "sources": [],
        "skip_retrieval": False,
        "llm_config": {},
        "org_id": None,
    }
    # Fetch org config to drive provider/model selection at runtime
    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = req.org_id or await conn.fetchval(
            "SELECT id FROM organizations WHERE slug='default'"
        )
        rows = await conn.fetch(
            "SELECT key, value FROM app_config WHERE org_id=$1", org_id
        ) if org_id else []
    llm_config = {r["key"]: r["value"] for r in rows}

    t0 = time.monotonic()
    try:
        final_state = await rag_graph.ainvoke(initial_state | {"llm_config": llm_config, "org_id": org_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    latency_ms = int((time.monotonic() - t0) * 1000)

    async with pool.acquire() as conn:
        if org_id is not None:
            await conn.execute(
                """
                INSERT INTO chat_logs
                    (org_id, session_id, user_message, assistant_response,
                     source_chunk_ids, loop_count, latency_ms, user_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                org_id,
                UUID(session_id),
                req.message,
                final_state["answer"],
                final_state["source_chunk_ids"],
                final_state["loop_count"],
                latency_ms,
                user["id"],
            )

    return ChatResponse(
        answer=final_state["answer"],
        source_chunk_ids=final_state["source_chunk_ids"],
        sources=final_state.get("sources", []),
        loop_count=final_state["loop_count"],
        session_id=session_id,
    )


@app.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(req: ChatRequest, request: Request):
    user = await require_user(request)
    session_id = req.session_id or str(uuid4())
    messages = req.history + [{"role": "user", "content": req.message}]

    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = req.org_id or await conn.fetchval(
            "SELECT id FROM organizations WHERE slug='default'"
        )
        rows = await conn.fetch(
            "SELECT key, value FROM app_config WHERE org_id=$1", org_id
        ) if org_id else []
    llm_config = {r["key"]: r["value"] for r in rows}

    initial_state = {
        "messages": messages,
        "query": req.message,
        "retrieved_docs": [],
        "grading_passed": False,
        "loop_count": 0,
        "answer": "",
        "source_chunk_ids": [],
        "sources": [],
        "skip_retrieval": False,
        "llm_config": llm_config,
        "org_id": org_id,
    }

    async def event_generator():
        t0 = time.monotonic()
        final_state: dict = {}
        try:
            async for event in rag_graph.astream_events(initial_state, version="v2"):
                if event["event"] == "on_custom_event" and event["name"] == "stream_token":
                    token = event["data"].get("token", "")
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                elif event["event"] == "on_chain_end" and event["name"] == "LangGraph":
                    final_state = event["data"].get("output", {})
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        latency_ms = int((time.monotonic() - t0) * 1000)

        log_id: int | None = None
        async with pool.acquire() as conn:
            if org_id is not None:
                log_id = await conn.fetchval(
                    """
                    INSERT INTO chat_logs
                        (org_id, session_id, user_message, assistant_response,
                         source_chunk_ids, loop_count, latency_ms, user_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                    RETURNING id
                    """,
                    org_id,
                    UUID(session_id),
                    req.message,
                    final_state.get("answer", ""),
                    final_state.get("source_chunk_ids", []),
                    final_state.get("loop_count", 0),
                    latency_ms,
                    user["id"],
                )

        yield f"data: {json.dumps({'type': 'done', 'log_id': log_id, 'answer': final_state.get('answer', ''), 'source_chunk_ids': final_state.get('source_chunk_ids', []), 'sources': final_state.get('sources', []), 'loop_count': final_state.get('loop_count', 0), 'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class FeedbackRequest(BaseModel):
    value: int  # 1 = thumbs up, -1 = thumbs down


@app.post("/chat/{log_id}/feedback", status_code=204)
@limiter.limit("60/minute")
async def submit_feedback(log_id: int, req: FeedbackRequest, request: Request):
    await require_user(request)
    if req.value not in (1, -1):
        raise HTTPException(status_code=422, detail="value must be 1 or -1")
    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchval(
            "UPDATE chat_logs SET feedback=$1 WHERE id=$2 RETURNING id",
            req.value,
            log_id,
        )
    if updated is None:
        raise HTTPException(status_code=404, detail="Log not found")


_SUGGEST_SYSTEM = (
    "You are a writing assistant helping a user draft a document. "
    "Based on the writing context and the reference document chunks provided, "
    "suggest the next paragraph or section that naturally continues the document. "
    "Write in the same tone and style as the existing content. "
    "Use only facts from the reference chunks — do not invent information. "
    "Output only the suggested text, no preamble or explanation."
)


@app.post("/suggest", response_model=SuggestResponse)
@limiter.limit("30/minute")
async def suggest(req: SuggestRequest, request: Request):
    await require_user(request)
    import asyncio
    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = req.org_id or await conn.fetchval(
            "SELECT id FROM organizations WHERE slug='default'"
        )
        rows = await conn.fetch(
            "SELECT key, value FROM app_config WHERE org_id=$1", org_id
        ) if org_id else []
    llm_config = {r["key"]: r["value"] for r in rows}

    query = req.context[-800:].strip()
    try:
        docs = await hybrid_search(query, top_k=5, org_id=org_id)
    except Exception:
        docs = []

    if docs:
        context_block = "\n\n".join(
            f"[{d.get('doc_title','Unknown')}]\n{d['text']}" for d in docs
        )
        prompt = f"Document so far:\n{req.context}\n\nReference material:\n{context_block}"
    else:
        prompt = f"Document so far:\n{req.context}"

    loop = asyncio.get_running_loop()
    try:
        suggestion = await loop.run_in_executor(
            None, lambda: llm_generate(prompt, _SUGGEST_SYSTEM, llm_config)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    sources = [
        {"doc_id": d["doc_id"], "doc_title": d.get("doc_title", ""), "doc_source": d.get("doc_source", "")}
        for d in docs
    ]
    seen: set[int] = set()
    unique_sources = [s for s in sources if not (s["doc_id"] in seen or seen.add(s["doc_id"]))]  # type: ignore[func-returns-value]

    return SuggestResponse(suggestion=suggestion, sources=unique_sources)


_FOLLOWUP_SYSTEM = (
    "You generate concise follow-up questions for a conversation. "
    "Output ONLY a raw JSON array of exactly 3 short question strings. "
    "No markdown, no explanation, no preamble — just the JSON array."
)


@app.post("/chat/followup", response_model=FollowUpResponse)
@limiter.limit("60/minute")
async def chat_followup(req: FollowUpRequest, request: Request):
    await require_user(request)
    import asyncio, json as _json
    recent = req.messages[-6:]
    history = "\n".join(
        f"{m['role'].upper()}: {str(m.get('content',''))[:400]}" for m in recent
    )
    prompt = (
        f"Conversation so far:\n{history}\n\n"
        "Generate 3 natural follow-up questions the user might want to ask next. "
        "Make them specific to what was discussed, not generic."
    )
    loop = asyncio.get_running_loop()
    try:
        # Always use Gemini for suggestions — fast, lightweight, unaffected
        # by the org's primary LLM provider setting or its credit balance.
        raw = await loop.run_in_executor(
            None, lambda: llm_generate(prompt, _FOLLOWUP_SYSTEM, {"llm_provider": "gemini"})
        )
        start, end = raw.index("["), raw.rindex("]") + 1
        suggestions = _json.loads(raw[start:end])[:3]
        suggestions = [s for s in suggestions if isinstance(s, str)]
    except Exception:
        suggestions = []
    return FollowUpResponse(suggestions=suggestions)


@app.get("/chat/sessions")
@limiter.limit("60/minute")
async def list_sessions(request: Request):
    user = await require_user(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT session_id,
                   MIN(user_message)           AS preview,
                   COUNT(*)                    AS message_count,
                   MAX(created_at)             AS last_active
            FROM chat_logs
            WHERE user_id = $1
            GROUP BY session_id
            ORDER BY last_active DESC
            LIMIT 50
            """,
            user["id"],
        )
    return {
        "sessions": [
            {
                "session_id": str(r["session_id"]),
                "preview": (r["preview"] or "")[:80],
                "message_count": r["message_count"],
                "last_active": r["last_active"].isoformat(),
            }
            for r in rows
        ]
    }


@app.get("/chat/sessions/{session_id}")
@limiter.limit("60/minute")
async def get_session(session_id: str, request: Request):
    user = await require_user(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_message, assistant_response,
                   source_chunk_ids, feedback, created_at
            FROM chat_logs
            WHERE session_id = $1 AND user_id = $2
            ORDER BY created_at ASC
            """,
            UUID(session_id),
            user["id"],
        )
    messages = []
    for r in rows:
        messages.append({
            "role": "user",
            "content": r["user_message"],
            "log_id": None,
            "source_chunk_ids": [],
            "sources": [],
            "feedback": None,
            "timestamp": r["created_at"].isoformat(),
        })
        messages.append({
            "role": "assistant",
            "content": r["assistant_response"],
            "log_id": r["id"],
            "source_chunk_ids": list(r["source_chunk_ids"] or []),
            "sources": [],
            "feedback": r["feedback"],
            "timestamp": r["created_at"].isoformat(),
        })
    return {"session_id": session_id, "messages": messages}


@app.post("/ingest/text", response_model=IngestResponse)
async def ingest_text_endpoint(req: IngestTextRequest):
    try:
        result = await ingest_text(
            text=req.text, title=req.title, source=req.source
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return IngestResponse(**result)


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename or "upload").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = await ingest_file(tmp_path, title=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return IngestResponse(**result)


@app.get("/health")
async def health():
    return {"status": "ok"}
