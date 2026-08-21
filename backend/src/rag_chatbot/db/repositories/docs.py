"""
Documents repository — database access for documents and chunks.

All SQL queries touching the documents and chunks tables live here.
Route handlers import these typed async functions instead of writing SQL inline.
"""

import asyncpg


async def get_document(
    conn: asyncpg.Connection,
    doc_id: int,
) -> asyncpg.Record | None:
    """
    Fetch a document row including its cached topics field.

    Args:
        conn: Active asyncpg connection or pool connection.
        doc_id: Primary key of the documents row.

    Returns:
        Record with id, title, topics columns, or None if not found.
    """
    return await conn.fetchrow("SELECT id, title, topics FROM documents WHERE id=$1", doc_id)


async def get_document_chunks(
    conn: asyncpg.Connection,
    doc_id: int,
    limit: int = 30,
) -> list[asyncpg.Record]:
    """
    Fetch the first N text chunks for a document in index order.

    Args:
        conn: Active asyncpg connection or pool connection.
        doc_id: Parent document primary key.
        limit: Maximum number of chunks to return (default 30).

    Returns:
        List of chunk records ordered by chunk_index ascending.
    """
    return await conn.fetch(
        "SELECT text FROM chunks WHERE doc_id=$1 ORDER BY chunk_index LIMIT $2",
        doc_id,
        limit,
    )


async def update_document_topics(
    conn: asyncpg.Connection,
    doc_id: int,
    topics_json: str,
) -> None:
    """
    Persist a computed topics JSON blob onto a document row.

    Args:
        conn: Active asyncpg connection or pool connection.
        doc_id: Primary key of the documents row to update.
        topics_json: JSON-serialised list of topic dicts.

    Returns:
        None
    """
    await conn.execute(
        "UPDATE documents SET topics=$1 WHERE id=$2",
        topics_json,
        doc_id,
    )
