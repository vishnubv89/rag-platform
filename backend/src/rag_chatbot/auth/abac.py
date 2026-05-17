"""
Attribute-Based Access Control (ABAC) — document-level access control.

A document is accessible to a user if for every label_type present on
the document, the user has at least one matching (attr_type, attr_value)
in user_attributes. Documents with no labels are accessible to all.
"""

from rag_chatbot.db.connection import get_pool


async def get_user_attributes(user_id: str) -> list[dict]:
    """Return [{attr_type, attr_value}] for the given user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT attr_type, attr_value FROM user_attributes WHERE user_id=$1",
            user_id,
        )
    return [dict(r) for r in rows]


async def label_document(doc_id: int, labels: list[dict]) -> None:
    """
    Attach labels to a document. Each label is {label_type, label_value}.
    Replaces existing labels of the same type.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for label in labels:
                await conn.execute(
                    """INSERT INTO document_labels (doc_id, label_type, label_value)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (doc_id, label_type, label_value) DO NOTHING""",
                    doc_id, label["label_type"], label["label_value"],
                )


async def get_document_labels(doc_id: int) -> list[dict]:
    """Return [{label_type, label_value}] for the given document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT label_type, label_value FROM document_labels WHERE doc_id=$1",
            doc_id,
        )
    return [dict(r) for r in rows]
