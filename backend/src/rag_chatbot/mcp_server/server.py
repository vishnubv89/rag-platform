"""
FastMCP server exposing RAG tools to any MCP-compatible client.

Run standalone for testing:
  fastmcp dev src/rag_chatbot/mcp_server/server.py

Or import `mcp` and mount it in FastAPI with SSE transport.
"""
import asyncio

from fastmcp import FastMCP

from rag_chatbot.db.connection import run_schema
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


@mcp.tool()
async def rerank_results(
    docs: list[dict], query: str, top_k: int = 5
) -> list[dict]:
    """
    Re-score and re-rank retrieved chunks by cosine similarity to the query embedding.

    Args:
        docs:  List of chunk dicts from hybrid_search (must have 'text' field).
        query: The original query string.
        top_k: How many top results to return.

    Returns:
        Re-ranked list of chunks.
    """
    from rag_chatbot.embeddings.gemini_embedder import embed_text
    import math

    query_vec = await embed_text(query, task_type="RETRIEVAL_QUERY")

    async def score(doc: dict) -> float:
        chunk_vec = await embed_text(doc["text"], task_type="RETRIEVAL_DOCUMENT")
        dot = sum(a * b for a, b in zip(query_vec, chunk_vec))
        mag_q = math.sqrt(sum(a * a for a in query_vec))
        mag_c = math.sqrt(sum(b * b for b in chunk_vec))
        return dot / (mag_q * mag_c + 1e-9)

    scored = [(doc, await score(doc)) for doc in docs]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [
        {**doc, "rerank_score": round(s, 4)}
        for doc, s in scored[:top_k]
    ]


if __name__ == "__main__":
    async def _setup():
        await run_schema()

    asyncio.run(_setup())
    mcp.run()
