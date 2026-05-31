"""
Sessions router — chat session listing and retrieval endpoints.

Handles GET /chat/sessions (list all sessions for the authenticated user) and
GET /chat/sessions/{session_id} (fetch the full message history for one session).
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from rag_chatbot.api.deps import require_user
from rag_chatbot.api.rate_limit import limiter
from rag_chatbot.db.connection import get_pool
from rag_chatbot.db.repositories.chat import get_session_messages, list_user_sessions

router = APIRouter(tags=["sessions"])


@router.get("/chat/sessions")
@limiter.limit("60/minute")
async def list_sessions(request: Request) -> dict:
    """Return a summary of the authenticated user's chat sessions, newest first."""
    user = await require_user(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await list_user_sessions(conn, user["id"])
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


@router.get("/chat/sessions/{session_id}")
@limiter.limit("60/minute")
async def get_session(session_id: str, request: Request) -> dict:
    """Return the interleaved user/assistant message history for a single session."""
    user = await require_user(request)
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid session_id format")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await get_session_messages(conn, session_uuid, user["id"])
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
