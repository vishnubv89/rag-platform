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


if __name__ == "__main__":
    async def _setup():
        await run_schema()

    asyncio.run(_setup())
    mcp.run()
