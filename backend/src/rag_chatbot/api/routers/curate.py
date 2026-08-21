"""
Curate router — knowledge article quality improvement and ServiceNow sync.

Handles POST /curate (LLM-powered KCS/ITIL improvement), GET /curate/categories
(fetch ServiceNow KB categories), and POST /curate/sync (write article to SN).
The _CURATE_SYSTEM prompt constant and all SN helper functions live in this module.
"""

import html as _html
import json as _json
import re as _re

from fastapi import APIRouter, HTTPException, Request

from rag_chatbot.api.deps import require_user
from rag_chatbot.api.rate_limit import limiter
from rag_chatbot.api.schemas import (
    CurateChange,
    CurateRequest,
    CurateResponse,
    CurateSyncRequest,
    CurateSyncResponse,
    SNCategory,
)
from rag_chatbot.db.connection import get_pool
from rag_chatbot.db.repositories.orgs import (
    get_org_llm_config,
    get_sn_connector_config,
    resolve_org_id,
)
from rag_chatbot.llm.client import generate as llm_generate
from rag_chatbot.retrieval.vector_store import hybrid_search

router = APIRouter(tags=["curate"])

_CURATE_SYSTEM = (
    "You are an expert knowledge-article quality curator applying KCS (Knowledge-Centered Service) "
    "v6 and ITIL 4 best-practice standards.\n\n"
    "Evaluate the provided document against these seven quality dimensions "
    "and return improvements:\n"
    "1. Structure — Has a clear title, purpose/scope, step-by-step procedure, "
    "expected outcome, and references section.\n"
    "2. Clarity — Plain language, active voice, no undefined acronyms or jargon.\n"
    "3. Completeness — All required sections present, no information gaps or dangling references.\n"
    "4. Accuracy — Consistent terminology, no contradictions, technically sound.\n"
    "5. Actionability — Numbered steps where applicable, specific instructions, "
    "measurable outcomes.\n"
    "6. Findability — Clear, search-friendly title with relevant keywords.\n"
    "7. Readability — Appropriate length, proper headings, scannable bullet points.\n\n"
    "SCORING RULES (mandatory):\n"
    "- Score on a 0–100 integer scale (e.g. 45, 72, 88). NEVER use fractions or decimals.\n"
    "- score_before = honest assessment of the original document BEFORE your changes.\n"
    "- score_after  = your realistic estimate of the improved document AFTER your changes.\n"
    "- score_after MUST be strictly greater than score_before. Minimum improvement: +10 points.\n"
    "- A typical raw KB article scores 20–55; a well-structured article scores 70–90.\n\n"
    "CHANGES RULES (mandatory):\n"
    "- You MUST list at least 3 improvements across different dimensions, "
    "even for decent articles.\n"
    "- Be specific: describe exactly what you changed and why it improves the dimension.\n\n"
    "Respond using EXACTLY this two-part format and no other text:\n\n"
    "METADATA\n"
    '{"improved_title":"...","score_before":N,"score_after":N,"changes":[{"dimension":"...","description":"..."}]}\n'
    "---CONTENT---\n"
    "<full improved document body here — plain text or markdown, no JSON escaping needed>\n\n"
    "Rules:\n"
    "- The METADATA JSON must be a single-line valid JSON object (no newlines inside it).\n"
    "- After ---CONTENT--- write the full improved document with normal markdown; "
    "do NOT escape anything.\n"
    "- If reference material is provided, incorporate relevant facts "
    "but do not invent information.\n"
    "- Rewrite the full document, not just a summary — the improved content must be complete."
)


def _text_to_sn_html(text: str) -> str:
    """Convert plain-text document to minimal ServiceNow-compatible HTML."""
    lines = text.splitlines()
    parts: list[str] = []
    buf: list[str] = []

    def flush_buf() -> None:
        if buf:
            para = " ".join(buf).strip()
            if para:
                parts.append(f"<p>{_html.escape(para)}</p>")
            buf.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_buf()
            continue
        if stripped.startswith("### "):
            flush_buf()
            parts.append(f"<h3>{_html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            flush_buf()
            parts.append(f"<h2>{_html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            flush_buf()
            parts.append(f"<h1>{_html.escape(stripped[2:])}</h1>")
        elif stripped.startswith(("- ", "* ", "• ")):
            flush_buf()
            parts.append(f"<li>{_html.escape(stripped[2:])}</li>")
        elif stripped[0].isdigit() and ". " in stripped[:5]:
            flush_buf()
            item = stripped.split(". ", 1)[-1]
            parts.append(f"<li>{_html.escape(item)}</li>")
        else:
            buf.append(stripped)

    flush_buf()
    return "\n".join(parts)


async def _get_sn_connector(org_id: int | None) -> dict:
    """
    Return the ServiceNow connector config dict for the given org.

    Args:
        org_id: Organisation whose active ServiceNow connector to retrieve.

    Returns:
        Config dictionary with instance_url, username, password, kb_sys_id etc.

    Raises:
        HTTPException 404 if no active connector is found.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await get_sn_connector_config(conn, org_id)
    if not row:
        raise HTTPException(
            status_code=404, detail="No active ServiceNow connector found for this org"
        )
    cfg = row["config"]
    return _json.loads(cfg) if isinstance(cfg, str) else dict(cfg)


@router.post("/curate", response_model=CurateResponse)
@limiter.limit("20/minute")
async def curate(req: CurateRequest, request: Request) -> CurateResponse:
    """Improve a document against KCS/ITIL industry quality standards."""
    import asyncio

    await require_user(request)

    pool = await get_pool()
    async with pool.acquire() as conn:
        org_id = await resolve_org_id(conn, user_org_id=None, request_org_id=req.org_id)
        llm_config = await get_org_llm_config(conn, org_id) if org_id else {}

    search_query = f"{req.title} {req.content[:600]}".strip()
    try:
        raw_docs = await hybrid_search(search_query, top_k=8, org_id=org_id)
        docs = [d for d in raw_docs if d.get("score", 0) >= 0.012][:5]
    except Exception:
        docs = []

    doc_header = f"Title: {req.title}\n\n" if req.title else ""
    if docs:
        ref_block = "\n\n".join(f"[{d.get('doc_title', 'Reference')}]\n{d['text']}" for d in docs)
        prompt = (
            f"Document to curate:\n{doc_header}{req.content}\n\n"
            f"Reference material from knowledge base:\n{ref_block}"
        )
    else:
        prompt = f"Document to curate:\n{doc_header}{req.content}"

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(
            None, lambda: llm_generate(prompt, _CURATE_SYSTEM, llm_config)
        )
    except Exception as e:
        msg = str(e)
        if "quota" in msg.lower() or "429" in msg or "resource_exhausted" in msg.lower():
            raise HTTPException(
                status_code=429,
                detail="LLM quota exceeded. Please wait a moment and try again.",
            )
        raise HTTPException(status_code=500, detail="Internal error")

    SPLIT = "---CONTENT---"
    raw = raw.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    improved_content_raw = ""
    if SPLIT in raw:
        meta_block, improved_content_raw = raw.split(SPLIT, 1)
        improved_content_raw = improved_content_raw.strip()
    else:
        meta_block = raw

    json_match = _re.search(r"\{.*\}", meta_block, _re.DOTALL)
    json_line = json_match.group(0) if json_match else None
    if not json_line:
        raise HTTPException(
            status_code=500,
            detail=f"LLM returned unparseable response: {meta_block[:200]}",
        )

    try:
        data = _json.loads(json_line)
    except _json.JSONDecodeError:
        try:
            data = _json.loads(json_line, strict=False)
        except _json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail=f"LLM metadata not valid JSON: {json_line[:200]}",
            )

    if not improved_content_raw:
        improved_content_raw = data.get("improved_content", req.content)

    changes = [
        CurateChange(dimension=c.get("dimension", ""), description=c.get("description", ""))
        for c in data.get("changes", [])
    ]
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

    score_before = max(1, min(100, int(data.get("score_before", 50))))
    score_after = max(1, min(100, int(data.get("score_after", 80))))
    if score_after <= score_before:
        score_after = min(100, score_before + 15)

    return CurateResponse(
        improved_title=data.get("improved_title", req.title),
        improved_content=improved_content_raw,
        changes=changes,
        score_before=score_before,
        score_after=score_after,
        sources=unique_sources,
    )


@router.get("/curate/categories", response_model=list[SNCategory])
@limiter.limit("30/minute")
async def curate_categories(request: Request, org_id: int | None = None) -> list[SNCategory]:
    """Fetch KB categories from the org's ServiceNow connector."""
    import httpx

    await require_user(request)
    cfg = await _get_sn_connector(org_id)

    kb_sys_id = cfg.get("kb_sys_id", "")
    params: dict = {
        "sysparm_fields": "sys_id,label",
        "sysparm_limit": 200,
    }
    if kb_sys_id:
        params["sysparm_query"] = f"kb_knowledge_base={kb_sys_id}"

    try:
        async with httpx.AsyncClient(
            base_url=cfg["instance_url"].rstrip("/"),
            auth=(cfg["username"], cfg["password"]),
            timeout=15,
        ) as client:
            r = await client.get("/api/now/table/kb_category", params=params)
            r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"ServiceNow error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ServiceNow unreachable: {e}")

    result = r.json().get("result", [])
    items = [result] if isinstance(result, dict) else result
    categories = [
        SNCategory(sys_id=item["sys_id"], label=item.get("label", item["sys_id"]))
        for item in items
        if item.get("sys_id")
    ]
    if not categories:
        categories = [SNCategory(sys_id="", label="(no category)")]
    return sorted(categories, key=lambda c: c.label)


@router.post("/curate/sync", response_model=CurateSyncResponse)
@limiter.limit("20/minute")
async def curate_sync(req: CurateSyncRequest, request: Request) -> CurateSyncResponse:
    """Push a curated document back to ServiceNow as a KB article."""
    import httpx

    await require_user(request)
    cfg = await _get_sn_connector(req.org_id)

    instance_url = cfg["instance_url"].rstrip("/")
    html_body = _text_to_sn_html(req.content)

    payload: dict = {
        "short_description": req.title,
        "text": html_body,
        "workflow_state": "published" if req.publish else "draft",
    }
    if cfg.get("kb_sys_id"):
        payload["kb_knowledge_base"] = cfg["kb_sys_id"]
    if req.category_sys_id:
        payload["kb_category"] = req.category_sys_id

    try:
        async with httpx.AsyncClient(
            base_url=instance_url,
            auth=(cfg["username"], cfg["password"]),
            timeout=30,
        ) as client:
            if req.external_id:
                r = await client.patch(
                    f"/api/now/table/kb_knowledge/{req.external_id}",
                    json=payload,
                )
            else:
                r = await client.post("/api/now/table/kb_knowledge", json=payload)
            r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"ServiceNow error {e.response.status_code}: {e.response.text[:300]}",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ServiceNow unreachable: {e}")

    result = r.json().get("result", {})
    item = result[0] if isinstance(result, list) else result
    sys_id = item.get("sys_id", req.external_id or "")
    url = f"{instance_url}/kb_view.do?sys_kb_id={sys_id}"
    action = "updated" if req.external_id else "created"

    return CurateSyncResponse(sys_id=sys_id, url=url, action=action)
