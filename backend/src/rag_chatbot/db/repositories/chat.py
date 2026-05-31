"""
Chat repository — database access for chat_logs and related session data.

All SQL queries touching chat_logs, session aggregations, and chat feedback
live here. Route handlers import these typed async functions instead of
writing SQL inline.
"""

from uuid import UUID

import asyncpg


async def insert_chat_log(
    conn: asyncpg.Connection,
    *,
    org_id: int,
    session_id: UUID,
    user_message: str,
    assistant_response: str,
    source_chunk_ids: list[int],
    loop_count: int,
    latency_ms: int,
    user_id: int,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """
    Insert a completed chat interaction into chat_logs.

    Args:
        conn: Active asyncpg connection or pool connection.
        org_id: Organisation that owns this chat log.
        session_id: UUID grouping messages into a conversation.
        user_message: The user's original message text.
        assistant_response: The final assistant answer.
        source_chunk_ids: IDs of chunks cited in the response.
        loop_count: Number of retrieval–grading loops executed.
        latency_ms: Total wall-clock latency in milliseconds.
        user_id: ID of the authenticated user.
        prompt_tokens: Token count for the prompt.
        completion_tokens: Token count for the completion.

    Returns:
        None
    """
    await conn.execute(
        """
        INSERT INTO chat_logs
            (org_id, session_id, user_message, assistant_response,
             source_chunk_ids, loop_count, latency_ms, user_id,
             prompt_tokens, completion_tokens)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        org_id,
        session_id,
        user_message,
        assistant_response,
        source_chunk_ids,
        loop_count,
        latency_ms,
        user_id,
        prompt_tokens,
        completion_tokens,
    )


async def insert_chat_log_returning_id(
    conn: asyncpg.Connection,
    *,
    org_id: int,
    session_id: UUID,
    user_message: str,
    assistant_response: str,
    source_chunk_ids: list[int],
    loop_count: int,
    latency_ms: int,
    user_id: int,
    prompt_tokens: int,
    completion_tokens: int,
) -> int | None:
    """
    Insert a chat log row and return its generated ID.

    Args:
        conn: Active asyncpg connection or pool connection.
        org_id: Organisation that owns this chat log.
        session_id: UUID grouping messages into a conversation.
        user_message: The user's original message text.
        assistant_response: The final assistant answer.
        source_chunk_ids: IDs of chunks cited in the response.
        loop_count: Number of retrieval–grading loops executed.
        latency_ms: Total wall-clock latency in milliseconds.
        user_id: ID of the authenticated user.
        prompt_tokens: Token count for the prompt.
        completion_tokens: Token count for the completion.

    Returns:
        The auto-generated integer ID of the new row, or None on failure.
    """
    return await conn.fetchval(
        """
        INSERT INTO chat_logs
            (org_id, session_id, user_message, assistant_response,
             source_chunk_ids, loop_count, latency_ms, user_id,
             prompt_tokens, completion_tokens)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        RETURNING id
        """,
        org_id,
        session_id,
        user_message,
        assistant_response,
        source_chunk_ids,
        loop_count,
        latency_ms,
        user_id,
        prompt_tokens,
        completion_tokens,
    )


async def update_chat_feedback(
    conn: asyncpg.Connection,
    log_id: int,
    value: int,
) -> int | None:
    """
    Set the feedback value on a chat_logs row.

    Args:
        conn: Active asyncpg connection or pool connection.
        log_id: Primary key of the chat_logs row to update.
        value: Feedback value — 1 (thumbs up) or -1 (thumbs down).

    Returns:
        The log_id if found and updated, or None if not found.
    """
    return await conn.fetchval(
        "UPDATE chat_logs SET feedback=$1 WHERE id=$2 RETURNING id",
        value,
        log_id,
    )


async def list_user_sessions(
    conn: asyncpg.Connection,
    user_id: int,
    limit: int = 50,
) -> list[asyncpg.Record]:
    """
    Return recent chat sessions for a user, ordered by most recent activity.

    Args:
        conn: Active asyncpg connection or pool connection.
        user_id: The authenticated user whose sessions to retrieve.
        limit: Maximum number of sessions to return (default 50).

    Returns:
        List of records with session_id, preview, message_count, last_active.
    """
    return await conn.fetch(
        """
        SELECT session_id,
               MIN(user_message)           AS preview,
               COUNT(*)                    AS message_count,
               MAX(created_at)             AS last_active
        FROM chat_logs
        WHERE user_id = $1
        GROUP BY session_id
        ORDER BY last_active DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )


async def get_session_messages(
    conn: asyncpg.Connection,
    session_id: UUID,
    user_id: int,
) -> list[asyncpg.Record]:
    """
    Fetch all chat log rows for a session belonging to a specific user.

    Args:
        conn: Active asyncpg connection or pool connection.
        session_id: The UUID identifying the conversation session.
        user_id: Scopes the query to the authenticated user's sessions.

    Returns:
        List of chat_logs records ordered by creation time ascending.
    """
    return await conn.fetch(
        """
        SELECT id, user_message, assistant_response,
               source_chunk_ids, feedback, created_at
        FROM chat_logs
        WHERE session_id = $1 AND user_id = $2
        ORDER BY created_at ASC
        """,
        session_id,
        user_id,
    )
