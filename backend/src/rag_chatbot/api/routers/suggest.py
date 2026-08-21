"""
Suggest router — writing assistance and document topic endpoints.

Handles POST /suggest (next-paragraph suggestions from KB context) and
GET /docs/{doc_id}/topics (lazily computed keyword topic clusters).
The _SUGGEST_SYSTEM and _FOLLOWUP_SYSTEM prompt constants, _keyword_topics
helper, and stopword set live in this module.
"""

import json
import re
from collections import Counter

from fastapi import APIRouter, HTTPException, Request

from rag_chatbot.api.deps import require_user
from rag_chatbot.api.rate_limit import limiter
from rag_chatbot.api.schemas import SuggestRequest, SuggestResponse
from rag_chatbot.db.connection import get_pool
from rag_chatbot.db.repositories.docs import (
    get_document,
    get_document_chunks,
    update_document_topics,
)
from rag_chatbot.db.repositories.orgs import get_default_org_id, get_org_llm_config
from rag_chatbot.llm.client import generate as llm_generate
from rag_chatbot.retrieval.vector_store import hybrid_search

router = APIRouter(tags=["suggest"])

_SUGGEST_SYSTEM = (
    "You are a writing assistant helping a user draft a document. "
    "Based on the writing context and the reference document chunks provided, "
    "suggest the next paragraph or section that naturally continues the document. "
    "Write in the same tone and style as the existing content. "
    "Use only facts from the reference chunks — do not invent information. "
    "Output only the suggested text, no preamble or explanation."
)

_TOPIC_COLORS = [
    "#4dabf7",
    "#69db7c",
    "#ffa94d",
    "#da77f2",
    "#ff6b6b",
    "#38d9a9",
    "#ffd43b",
    "#a9e34b",
]

_STOP = frozenset(
    "a an the and or but in on at to of for is are was were be been being "
    "have has had do does did will would could should may might shall can "
    "with by from as into through during before after above below between "
    "this that these those it its we they them their he she him her "
    "i me my you your we our us not no nor so yet both either neither "
    "just also only then than when where which who whom what how "
    "all any each few more most other some such no nor not only own "
    "same so than too very s t can will just don should now d ll m o re ve "
    "figure table section et al e g i e vs".split()
)


def _keyword_topics(chunks: list[str], n_topics: int = 7) -> list[dict]:
    """
    Extract topic clusters from chunk texts via bigram frequency.

    Pure-Python fallback used when no cached topics exist and the LLM is
    unavailable. Returns up to n_topics entries with label + subtopics.

    Args:
        chunks: List of plain-text chunk strings.
        n_topics: Maximum number of topic clusters to return (default 7).

    Returns:
        List of dicts with 'label' (str) and 'subtopics' (list[str]) keys.
    """
    all_text = " ".join(chunks).lower()
    words = re.findall(r"[a-z][a-z\-]{2,}", all_text)
    words = [w for w in words if w not in _STOP and len(w) > 3]
    uni = Counter(words)
    bi = Counter(
        f"{words[i]} {words[i + 1]}"
        for i in range(len(words) - 1)
        if words[i] not in _STOP and words[i + 1] not in _STOP
    )
    seen: set[str] = set()
    topics: list[dict] = []
    for phrase, _ in bi.most_common(n_topics * 2):
        if len(topics) >= n_topics:
            break
        w1, w2 = phrase.split()
        if w1 in seen or w2 in seen:
            continue
        seen.update([w1, w2])
        subs = [w for w, _ in uni.most_common(50) if w not in seen and w not in {w1, w2}][:3]
        seen.update(subs)
        topics.append({"label": phrase.title(), "subtopics": [s.capitalize() for s in subs]})
    return topics


@router.post("/suggest", response_model=SuggestResponse)
@limiter.limit("30/minute")
async def suggest(req: SuggestRequest, request: Request) -> SuggestResponse:
    """Suggest the next paragraph for a document in progress using KB context."""
    import asyncio

    await require_user(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = req.org_id or await get_default_org_id(conn)
        llm_config = await get_org_llm_config(conn, org_id) if org_id else {}

    query = req.context[-800:].strip()
    try:
        docs = await hybrid_search(query, top_k=5, org_id=org_id)
    except Exception:
        docs = []

    if docs:
        context_block = "\n\n".join(f"[{d.get('doc_title', 'Unknown')}]\n{d['text']}" for d in docs)
        prompt = f"Document so far:\n{req.context}\n\nReference material:\n{context_block}"
    else:
        prompt = f"Document so far:\n{req.context}"

    loop = asyncio.get_running_loop()
    try:
        suggestion = await loop.run_in_executor(
            None, lambda: llm_generate(prompt, _SUGGEST_SYSTEM, llm_config)
        )
    except Exception as e:
        msg = str(e)
        if "quota" in msg.lower() or "429" in msg or "resource_exhausted" in msg.lower():
            raise HTTPException(
                status_code=429, detail="LLM quota exceeded. Please wait a moment."
            ) from e
        raise HTTPException(status_code=500, detail="Internal error") from e

    sources = [
        {
            "doc_id": d["doc_id"],
            "doc_title": d.get("doc_title", ""),
            "doc_source": d.get("doc_source", ""),
        }
        for d in docs
    ]
    seen: set[int] = set()
    unique_sources = [s for s in sources if not (s["doc_id"] in seen or seen.add(s["doc_id"]))]  # type: ignore[func-returns-value]

    return SuggestResponse(suggestion=suggestion, sources=unique_sources)


@router.get("/docs/{doc_id}/topics")
@limiter.limit("30/minute")
async def get_doc_topics(request: Request, doc_id: int) -> dict:
    """
    Return (or lazily compute) topic clusters for a document.

    Results are cached in documents.topics — keyword extraction runs when
    the column is NULL.  No LLM call is made from this endpoint.
    """
    await require_user(request)
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await get_document(conn, doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    if row["topics"] is not None:
        raw = row["topics"] if isinstance(row["topics"], list) else json.loads(row["topics"])
    else:
        async with pool.acquire() as conn:
            chunks = await get_document_chunks(conn, doc_id, limit=30)
        if not chunks:
            return {"doc_id": doc_id, "title": row["title"], "topics": []}

        raw = _keyword_topics([c["text"] for c in chunks])
        async with pool.acquire() as conn:
            await update_document_topics(conn, doc_id, json.dumps(raw))

    topics = [{**t, "color": _TOPIC_COLORS[i % len(_TOPIC_COLORS)]} for i, t in enumerate(raw)]
    return {"doc_id": doc_id, "title": row["title"], "topics": topics}
