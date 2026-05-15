import asyncio
import json
import sys
from pathlib import Path

from rag_chatbot.db.connection import get_pool, run_schema
from rag_chatbot.embeddings.gemini_embedder import embed_batch
from rag_chatbot.ingestion.chunker import semantic_chunk_text as chunk_text
from rag_chatbot.ingestion.loader import load_file


async def ingest_file(
    file_path: str | Path,
    title: str | None = None,
    source: str = "",
    metadata: dict | None = None,
    org_id: int | None = None,
) -> dict:
    """Load, chunk, embed, and store a file atomically. Returns doc info."""
    p = Path(file_path)
    title = title or p.stem
    text = load_file(p)
    chunks = chunk_text(text)

    if not chunks:
        raise ValueError(f"No text could be extracted from {file_path}")

    embeddings = await embed_batch(chunks, task_type="RETRIEVAL_DOCUMENT")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Wrap both INSERTs in a transaction — if embedding or chunk insert
        # fails, the document row is rolled back too (no orphan 0-chunk docs).
        async with conn.transaction():
            doc_id = await conn.fetchval(
                "INSERT INTO documents (title, source, metadata, org_id) VALUES ($1, $2, $3, $4) RETURNING id",
                title,
                source or str(p),
                json.dumps(metadata or {}),
                org_id,
            )
            await conn.executemany(
                "INSERT INTO chunks (doc_id, chunk_index, text, embedding) VALUES ($1, $2, $3, $4)",
                [(doc_id, i, chunk, embeddings[i]) for i, chunk in enumerate(chunks)],
            )

    return {"doc_id": doc_id, "title": title, "chunks": len(chunks)}


async def ingest_text(
    text: str,
    title: str,
    source: str = "",
    metadata: dict | None = None,
    org_id: int | None = None,
) -> dict:
    """Chunk, embed, and store raw text content atomically."""
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No chunks extracted from provided text")

    embeddings = await embed_batch(chunks, task_type="RETRIEVAL_DOCUMENT")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            doc_id = await conn.fetchval(
                "INSERT INTO documents (title, source, metadata, org_id) VALUES ($1, $2, $3, $4) RETURNING id",
                title,
                source,
                json.dumps(metadata or {}),
                org_id,
            )
            await conn.executemany(
                "INSERT INTO chunks (doc_id, chunk_index, text, embedding) VALUES ($1, $2, $3, $4)",
                [(doc_id, i, chunk, embeddings[i]) for i, chunk in enumerate(chunks)],
            )

    return {"doc_id": doc_id, "title": title, "chunks": len(chunks)}


if __name__ == "__main__":
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python -m rag_chatbot.ingestion.pipeline <file>")
            sys.exit(1)
        await run_schema()
        result = await ingest_file(sys.argv[1])
        print(f"Ingested: {result}")

    asyncio.run(main())
