from pgvector.asyncpg import register_vector

from rag_chatbot.db.connection import get_pool
from rag_chatbot.embeddings.gemini_embedder import embed_text
from rag_chatbot.config import settings

_HYBRID_SQL = """
WITH bm25 AS (
    SELECT
        c.id,
        c.doc_id,
        c.text,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank(c.search_vec, plainto_tsquery('english', $1)) DESC
        ) AS rank
    FROM chunks c
    WHERE c.search_vec @@ plainto_tsquery('english', $1)
    LIMIT 20
),
semantic AS (
    SELECT
        c.id,
        c.doc_id,
        c.text,
        ROW_NUMBER() OVER (ORDER BY c.embedding <=> $2::vector) AS rank
    FROM chunks c
    ORDER BY c.embedding <=> $2::vector
    LIMIT 20
),
fused AS (
    SELECT
        COALESCE(b.id,     s.id)     AS chunk_id,
        COALESCE(b.doc_id, s.doc_id) AS doc_id,
        COALESCE(b.text,   s.text)   AS text,
        1.0 / (60 + COALESCE(b.rank, 999)) +
        1.0 / (60 + COALESCE(s.rank, 999)) AS rrf_score
    FROM bm25 b
    FULL OUTER JOIN semantic s ON b.id = s.id
)
SELECT
    f.chunk_id,
    f.doc_id,
    f.text,
    f.rrf_score,
    d.title     AS doc_title,
    d.source    AS doc_source,
    d.external_id
FROM fused f
JOIN documents d ON d.id = f.doc_id
WHERE ($4::bigint IS NULL OR d.org_id = $4)
ORDER BY f.rrf_score DESC
LIMIT $3
"""


async def hybrid_search(query: str, top_k: int | None = None, org_id: int | None = None) -> list[dict]:
    """BM25 + semantic search fused via Reciprocal Rank Fusion."""
    k = top_k or settings.retrieval_top_k
    query_embedding = await embed_text(query, task_type="RETRIEVAL_QUERY")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_HYBRID_SQL, query, query_embedding, k, org_id)

    # Deduplicate: same article ingested from multiple connectors gets the same
    # external_id. Keep only the highest-scored chunk per unique article.
    seen: set[str] = set()
    results: list[dict] = []
    for row in rows:
        dedup_key = row["external_id"] or f"{row['doc_title']}:{row['doc_id']}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        results.append({
            "chunk_id": row["chunk_id"],
            "doc_id": row["doc_id"],
            "text": row["text"],
            "score": float(row["rrf_score"]),
            "doc_title": row["doc_title"] or "",
            "doc_source": row["doc_source"] or "",
        })
    return results
