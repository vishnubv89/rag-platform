"""
Chat router — core conversation endpoints.

Handles POST /chat (non-streaming), POST /chat/stream (SSE),
POST /chat/followup (follow-up question suggestions), and
POST /chat/{log_id}/feedback. Langfuse trace/span context propagation
is preserved exactly as originally implemented.
"""

import json
import logging
import time
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from rag_chatbot.agent.graph import rag_graph
from rag_chatbot.api.deps import extract_zitadel_token, require_user
from rag_chatbot.api.rate_limit import limiter
from rag_chatbot.api.schemas import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    FollowUpRequest,
    FollowUpResponse,
)
from rag_chatbot.db.connection import get_pool
from rag_chatbot.db.repositories.chat import (
    insert_chat_log,
    insert_chat_log_returning_id,
    update_chat_feedback,
)
from rag_chatbot.db.repositories.orgs import get_org_llm_config, resolve_org_id
from rag_chatbot.llm.client import generate as llm_generate
from rag_chatbot.observability import get_langfuse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

_FOLLOWUP_SYSTEM = (
    "You generate concise follow-up questions for a conversation. "
    "Output ONLY a raw JSON array of exactly 3 short question strings. "
    "No markdown, no explanation, no preamble — just the JSON array."
)


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    """Run a full RAG pipeline turn and return the complete answer."""
    user = await require_user(request)
    try:
        session_id = str(UUID(req.session_id)) if req.session_id else str(uuid4())
    except ValueError:
        session_id = str(uuid4())

    messages = req.history + [{"role": "user", "content": req.message}]
    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = await resolve_org_id(
            conn,
            user_org_id=user.get("org_id"),
            request_org_id=req.org_id,
        )
        llm_config = await get_org_llm_config(conn, org_id) if org_id else {}

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
        "kb_overview": False,
        "llm_config": llm_config,
        "org_id": org_id,
        "user_zitadel_token": extract_zitadel_token(request),
        "action_intent": None,
        "action_params": {},
        "action_result": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }

    lf = get_langfuse()
    t0 = time.monotonic()
    try:
        from langfuse._client.propagation import _propagate_attributes

        _state = initial_state | {"llm_config": llm_config, "org_id": org_id}
        if lf:
            with _propagate_attributes(
                user_id=str(user.get("id")),
                session_id=session_id,
                tags=[f"org:{org_id}"] if org_id else [],
                metadata={"org_id": str(org_id)} if org_id else {},
            ):
                with lf.start_as_current_observation(
                    name="rag-chat",
                    as_type="chain",
                    input={"query": req.message},
                ) as trace:
                    final_state = await rag_graph.ainvoke(_state)
                    trace.update(output={"answer": final_state.get("answer", "")})
        else:
            final_state = await rag_graph.ainvoke(_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error") from e

    latency_ms = int((time.monotonic() - t0) * 1000)

    async with pool.acquire() as conn:
        if org_id is not None:
            await insert_chat_log(
                conn,
                org_id=org_id,
                session_id=UUID(session_id),
                user_message=req.message,
                assistant_response=final_state["answer"],
                source_chunk_ids=final_state["source_chunk_ids"],
                loop_count=final_state["loop_count"],
                latency_ms=latency_ms,
                user_id=user["id"],
                prompt_tokens=final_state.get("prompt_tokens", 0),
                completion_tokens=final_state.get("completion_tokens", 0),
            )

    return ChatResponse(
        answer=final_state["answer"],
        source_chunk_ids=final_state["source_chunk_ids"],
        sources=final_state.get("sources", []),
        loop_count=final_state["loop_count"],
        session_id=session_id,
    )


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
    """Stream RAG pipeline tokens via Server-Sent Events."""
    user = await require_user(request)
    try:
        session_id = str(UUID(req.session_id)) if req.session_id else str(uuid4())
    except ValueError:
        session_id = str(uuid4())

    messages = req.history + [{"role": "user", "content": req.message}]
    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = await resolve_org_id(
            conn,
            user_org_id=user.get("org_id"),
            request_org_id=req.org_id,
        )
        llm_config = await get_org_llm_config(conn, org_id) if org_id else {}

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
        "kb_overview": False,
        "llm_config": llm_config,
        "org_id": org_id,
        "user_zitadel_token": extract_zitadel_token(request),
        "action_intent": None,
        "action_params": {},
        "action_result": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }

    lf = get_langfuse()

    async def event_generator():
        from langfuse._client.propagation import _propagate_attributes

        t0 = time.monotonic()
        final_state: dict = {}
        lf_trace = None
        _prop_ctx = None
        if lf:
            _prop_ctx = _propagate_attributes(
                user_id=str(user.get("id")),
                session_id=session_id,
                tags=[f"org:{org_id}"] if org_id else [],
                metadata={"org_id": str(org_id)} if org_id else {},
            )
            _prop_ctx.__enter__()
            lf_trace = lf.start_observation(
                name="rag-chat-stream",
                as_type="chain",
                input={"query": req.message},
            )
        try:
            async for event in rag_graph.astream_events(initial_state, version="v2"):
                if event["event"] == "on_custom_event" and event["name"] == "stream_token":
                    token = event["data"].get("token", "")
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                elif event["event"] == "on_chain_end" and event["name"] == "LangGraph":
                    final_state = event["data"].get("output", {})
        except Exception as e:
            if lf_trace:
                lf_trace.end()
            if _prop_ctx:
                _prop_ctx.__exit__(None, None, None)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        if lf_trace:
            lf_trace.update(output={"answer": final_state.get("answer", "")})
            lf_trace.end()
        if _prop_ctx:
            _prop_ctx.__exit__(None, None, None)

        latency_ms = int((time.monotonic() - t0) * 1000)

        log_id: int | None = None
        async with pool.acquire() as conn:
            if org_id is not None:
                log_id = await insert_chat_log_returning_id(
                    conn,
                    org_id=org_id,
                    session_id=UUID(session_id),
                    user_message=req.message,
                    assistant_response=final_state.get("answer", ""),
                    source_chunk_ids=final_state.get("source_chunk_ids", []),
                    loop_count=final_state.get("loop_count", 0),
                    latency_ms=latency_ms,
                    user_id=user["id"],
                    prompt_tokens=final_state.get("prompt_tokens", 0),
                    completion_tokens=final_state.get("completion_tokens", 0),
                )

        done_payload = {
            "type": "done",
            "log_id": log_id,
            "answer": final_state.get("answer", ""),
            "source_chunk_ids": final_state.get("source_chunk_ids", []),
            "sources": final_state.get("sources", []),
            "loop_count": final_state.get("loop_count", 0),
            "session_id": session_id,
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/followup", response_model=FollowUpResponse)
@limiter.limit("60/minute")
async def chat_followup(req: FollowUpRequest, request: Request) -> FollowUpResponse:
    """Generate three follow-up questions based on the recent conversation history."""
    import asyncio
    import json as _json

    await require_user(request)
    recent = req.messages[-6:]
    history = "\n".join(f"{m['role'].upper()}: {str(m.get('content', ''))[:400]}" for m in recent)
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


@router.post("/chat/{log_id}/feedback", status_code=204)
@limiter.limit("60/minute")
async def submit_feedback(log_id: int, req: FeedbackRequest, request: Request) -> None:
    """Record thumbs-up (1) or thumbs-down (-1) feedback on a chat log entry."""
    await require_user(request)
    if req.value not in (1, -1):
        raise HTTPException(status_code=422, detail="value must be 1 or -1")
    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await update_chat_feedback(conn, log_id, req.value)
    if updated is None:
        raise HTTPException(status_code=404, detail="Log not found")
