"""
FastMCP server exposing RAG tools to any MCP-compatible client.

Run standalone for testing:
  fastmcp dev src/rag_chatbot/mcp_server/server.py

Or import `mcp` and mount it in FastAPI with SSE transport.
"""
import asyncio
import math

from fastmcp import FastMCP

from rag_chatbot.db.connection import run_schema
from rag_chatbot.embeddings.gemini_embedder import embed_text, embed_batch
from rag_chatbot.ingestion.pipeline import ingest_text
from rag_chatbot.retrieval.vector_store import hybrid_search as _hybrid_search

mcp = FastMCP(
    name="rag-server",
    instructions=(
        "Use hybrid_search to find relevant document chunks before answering. "
        "Use ingest_document to add new knowledge to the knowledge base."
    ),
)


@mcp.tool()
async def hybrid_search(query: str, top_k: int = 8) -> list[dict]:
    """
    Search the knowledge base using hybrid BM25 + semantic search (RRF fusion).

    Args:
        query: The search query string.
        top_k: Maximum number of chunks to return (default 8).

    Returns:
        List of chunks with chunk_id, doc_id, text, and rrf_score.
    """
    return await _hybrid_search(query, top_k=top_k)


@mcp.tool()
async def ingest_document(title: str, text: str, source: str = "") -> dict:
    """
    Add a new document to the knowledge base.

    Args:
        title: Human-readable document title.
        text:  Full text content of the document.
        source: Optional URL or file path for provenance.

    Returns:
        doc_id, title, and chunk count.
    """
    return await ingest_text(text=text, title=title, source=source)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@mcp.tool()
async def rerank_results(docs: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """
    Re-rank retrieved chunks by cosine similarity to the query.

    Args:
        docs:  List of chunk dicts (must each contain a 'text' field).
        query: The search query to rank against.
        top_k: Maximum number of chunks to return (default 5).

    Returns:
        Top-K chunks sorted descending by rerank_score (cosine similarity).
        Each dict is the original chunk dict with a 'rerank_score' field added.
    """
    if not docs:
        return []

    query_vec = await embed_text(query, task_type="RETRIEVAL_QUERY")
    texts = [d.get("text", "") for d in docs]
    chunk_vecs = await embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")

    scored = [
        {**doc, "rerank_score": _cosine(query_vec, vec)}
        for doc, vec in zip(docs, chunk_vecs)
    ]
    scored.sort(key=lambda d: d["rerank_score"], reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    async def _setup():
        await run_schema()

    asyncio.run(_setup())
    mcp.run()
