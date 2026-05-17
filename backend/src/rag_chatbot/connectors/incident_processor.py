"""
Processes ServiceNow closed incidents into Knowledge Base articles.

Pipeline:
  1. Fetch all closed/resolved incidents (+ work notes)
  2. Determine which sys_ids are already ingested (via document metadata)
  3. Run hybrid clustering on new incidents:
       a. Group by category + subcategory
       b. Within each group, semantic sub-clustering (cosine threshold 0.72)
  4. Generate a "Known Issue / Resolution" KB article per qualifying cluster (≥3 incidents)
  5. Upsert generated articles through the standard chunks+embeddings pipeline
"""
import json
import logging
import math
from datetime import datetime, timezone

from rag_chatbot.connectors.servicenow import IncidentRecord, ServiceNowConnector
from rag_chatbot.embeddings.gemini_embedder import embed_batch
from rag_chatbot.llm.client import generate

log = logging.getLogger(__name__)

MIN_CLUSTER_SIZE = 3
COSINE_THRESHOLD = 0.72

_ARTICLE_SYSTEM = (
    "You are a technical knowledge base author. Write clear, factual, actionable articles. "
    "Do not mention specific ticket numbers, dates, or individual names."
)

_ARTICLE_PROMPT_TEMPLATE = """\
Summarise the following {n} resolved ServiceNow incidents into a knowledge base article.
Category: {category} / {subcategory}

INCIDENTS
---------
{incidents_text}

Write the article using EXACTLY this structure (no extra sections):

## <Descriptive Title for this class of issue>

**Summary**
2-3 sentences describing the problem pattern seen across these incidents.

**Symptoms**
- Bullet list of what users typically report

**Root Cause**
Brief explanation of the underlying cause (write "Varies" if inconsistent).

**Resolution Steps**
1. Numbered step-by-step fix that resolved most of these incidents

**Prevention**
How to avoid recurrence (omit section if not applicable).
"""


# ── helpers ────────────────────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _incident_embed_text(inc: IncidentRecord) -> str:
    """Compact representation used for embedding — keeps tokens down."""
    parts = [inc.short_description, inc.description, inc.resolution_notes]
    parts.extend(inc.work_notes[:3])  # first 3 work notes is enough signal
    return " ".join(p.strip() for p in parts if p.strip())[:2000]


def _incident_article_text(inc: IncidentRecord) -> str:
    """Full representation used inside the LLM prompt."""
    lines = [f"Short description: {inc.short_description}"]
    if inc.description and inc.description != inc.short_description:
        lines.append(f"Description: {inc.description[:500]}")
    if inc.resolution_notes:
        lines.append(f"Resolution: {inc.resolution_notes[:500]}")
    if inc.work_notes:
        notes = " | ".join(n[:200] for n in inc.work_notes[:5])
        lines.append(f"Work notes: {notes}")
    return "\n".join(lines)


# ── clustering ─────────────────────────────────────────────────────────────────

async def _semantic_subclusters(
    members: list[IncidentRecord],
) -> dict[int, list[IncidentRecord]]:
    """Greedy single-pass semantic clustering within a category group."""
    texts = [_incident_embed_text(m) for m in members]
    embeddings = await embed_batch(texts, task_type="RETRIEVAL_DOCUMENT")

    cluster_seeds: list[list[float]] = []   # representative embedding per cluster
    assigned: list[int] = []

    for emb in embeddings:
        best_sim, best_c = -1.0, -1
        for c_idx, seed in enumerate(cluster_seeds):
            sim = _cosine(emb, seed)
            if sim > best_sim:
                best_sim, best_c = sim, c_idx

        if best_sim >= COSINE_THRESHOLD:
            assigned.append(best_c)
        else:
            assigned.append(len(cluster_seeds))
            cluster_seeds.append(emb)

    sub: dict[int, list[IncidentRecord]] = {}
    for inc, c_id in zip(members, assigned):
        sub.setdefault(c_id, []).append(inc)
    return sub


async def cluster_incidents(
    incidents: list[IncidentRecord],
) -> dict[str, list[IncidentRecord]]:
    """
    Hybrid clustering returning {cluster_key: [IncidentRecord, ...]}.
    Only clusters with ≥ MIN_CLUSTER_SIZE incidents are returned.
    """
    # Step 1 — group by category + subcategory
    groups: dict[str, list[IncidentRecord]] = {}
    for inc in incidents:
        key = f"{inc.category or 'general'}__{inc.subcategory or 'general'}"
        groups.setdefault(key, []).append(inc)

    clusters: dict[str, list[IncidentRecord]] = {}
    for group_key, members in groups.items():
        # Step 2 — semantic sub-clustering within group
        sub = await _semantic_subclusters(members)
        for c_id, sub_members in sub.items():
            if len(sub_members) >= MIN_CLUSTER_SIZE:
                clusters[f"{group_key}__{c_id}"] = sub_members

    return clusters


# ── article generation ─────────────────────────────────────────────────────────

def _generate_article(
    cluster_key: str,
    members: list[IncidentRecord],
    llm_config: dict,
) -> str:
    parts = cluster_key.split("__")
    category = parts[0].replace("_", " ").title() if parts else "General"
    subcategory = parts[1].replace("_", " ").title() if len(parts) > 1 else "General"

    incidents_text = "\n\n".join(
        f"Incident {i + 1}:\n{_incident_article_text(m)}"
        for i, m in enumerate(members)
    )
    prompt = _ARTICLE_PROMPT_TEMPLATE.format(
        n=len(members),
        category=category,
        subcategory=subcategory,
        incidents_text=incidents_text,
    )
    return generate(prompt, system=_ARTICLE_SYSTEM, config=llm_config or {})


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def _already_processed_sys_ids(conn, connector_id: int) -> set[str]:
    """Return all incident sys_ids already captured in cluster documents."""
    rows = await conn.fetch(
        "SELECT metadata FROM documents WHERE connector_id=$1 AND metadata::text LIKE '%incident_sys_ids%'",
        connector_id,
    )
    seen: set[str] = set()
    for row in rows:
        try:
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
            seen.update(meta.get("incident_sys_ids", []))
        except Exception:
            pass
    return seen


async def _existing_cluster_doc(conn, connector_id: int, cluster_key: str) -> int | None:
    """Return doc_id of existing document for this cluster, or None."""
    row = await conn.fetchrow(
        "SELECT id FROM documents WHERE connector_id=$1 AND metadata::text LIKE $2",
        connector_id, f'%"cluster_key": "{cluster_key}"%',
    )
    return row["id"] if row else None


async def _upsert_cluster_doc(
    conn,
    connector_id: int,
    org_id: int,
    cluster_key: str,
    title: str,
    text: str,
    sys_ids: list[str],
    instance_url: str,
    existing_doc_id: int | None,
) -> None:
    from rag_chatbot.embeddings.gemini_embedder import embed_batch as _eb
    from rag_chatbot.ingestion.chunker import chunk_text as _ct

    now = datetime.now(timezone.utc)
    meta = json.dumps({
        "source": "servicenow_incidents",
        "cluster_key": cluster_key,
        "incident_sys_ids": sys_ids,
        "connector_id": connector_id,
        "generated_at": now.isoformat(),
    })
    import hashlib
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    source_url = f"{instance_url.rstrip('/')}/incident_list.do"

    if existing_doc_id:
        existing_hash = await conn.fetchval(
            "SELECT content_hash FROM documents WHERE id=$1", existing_doc_id
        )
        if existing_hash == content_hash:
            return  # no change
        await conn.execute(
            """UPDATE documents SET title=$1, metadata=$2, content_hash=$3,
               last_synced_at=$4 WHERE id=$5""",
            title, meta, content_hash, now, existing_doc_id,
        )
        await conn.execute("DELETE FROM chunks WHERE doc_id=$1", existing_doc_id)
        doc_id = existing_doc_id
    else:
        doc_id = await conn.fetchval(
            """INSERT INTO documents (title, source, metadata, org_id, connector_id,
               external_id, content_hash, last_synced_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id""",
            title, source_url, meta, org_id, connector_id,
            f"incident_cluster__{cluster_key}", content_hash, now,
        )

    chunks = _ct(text)
    if chunks:
        embeddings = await _eb(chunks, task_type="RETRIEVAL_DOCUMENT")
        await conn.executemany(
            "INSERT INTO chunks (doc_id, chunk_index, text, embedding) VALUES ($1,$2,$3,$4)",
            [(doc_id, i, chunk, emb) for i, (chunk, emb) in enumerate(zip(chunks, embeddings))],
        )


# ── main entry point ───────────────────────────────────────────────────────────

async def process_incidents(
    pool,
    connector_id: int,
    org_id: int,
    config: dict,
    llm_config: dict,
) -> dict:
    """
    Fetch, cluster, and ingest ServiceNow incidents as KB articles.
    Returns stats dict.
    """
    stats = {"clusters_created": 0, "clusters_updated": 0, "incidents_processed": 0, "error": None}

    try:
        connector = ServiceNowConnector(config)

        log.info("Fetching closed incidents for connector %d", connector_id)
        incidents = await connector.list_closed_incidents()
        log.info("  %d incidents fetched", len(incidents))

        if not incidents:
            return stats

        # Enrich with work notes (batch: run concurrently per incident)
        import asyncio
        async def _enrich(inc: IncidentRecord) -> IncidentRecord:
            try:
                inc.work_notes = await connector.fetch_work_notes(inc.sys_id)
            except Exception:
                inc.work_notes = []
            return inc

        incidents = await asyncio.gather(*[_enrich(inc) for inc in incidents])

        # Determine which sys_ids are already fully ingested
        async with pool.acquire() as conn:
            already_done = await _already_processed_sys_ids(conn, connector_id)

        new_incidents = [inc for inc in incidents if inc.sys_id not in already_done]
        log.info("  %d new incidents to process", len(new_incidents))

        if not new_incidents:
            return stats

        # Cluster new incidents
        clusters = await cluster_incidents(list(new_incidents))
        log.info("  %d qualifying clusters found", len(clusters))

        instance_url = config.get("instance_url", "")

        for cluster_key, members in clusters.items():
            try:
                article_text = _generate_article(cluster_key, members, llm_config)

                # Extract title from first markdown heading
                title = "ServiceNow Incidents: " + cluster_key.replace("__", " / ")
                for line in article_text.splitlines():
                    line = line.strip()
                    if line.startswith("## "):
                        title = line[3:].strip()
                        break

                sys_ids = [m.sys_id for m in members]

                async with pool.acquire() as conn:
                    existing_id = await _existing_cluster_doc(conn, connector_id, cluster_key)
                    await _upsert_cluster_doc(
                        conn,
                        connector_id=connector_id,
                        org_id=org_id,
                        cluster_key=cluster_key,
                        title=title,
                        text=article_text,
                        sys_ids=sys_ids,
                        instance_url=instance_url,
                        existing_doc_id=existing_id,
                    )

                if existing_id:
                    stats["clusters_updated"] += 1
                else:
                    stats["clusters_created"] += 1
                stats["incidents_processed"] += len(members)

            except Exception as exc:
                log.exception("Failed to process cluster %s", cluster_key)
                stats["error"] = str(exc)

    except Exception as exc:
        log.exception("Incident processing failed for connector %d", connector_id)
        stats["error"] = str(exc)

    return stats
