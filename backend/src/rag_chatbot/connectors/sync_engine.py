"""
Sync engine — runs connector syncs on schedule and on-demand.

Lifecycle:
  start_scheduler()   called once at app startup (lifespan)
  stop_scheduler()    called at shutdown
  run_sync(connector_id)  trigger an immediate sync for one connector
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from rag_chatbot.db.connection import get_pool
from rag_chatbot.embeddings.gemini_embedder import embed_batch
from rag_chatbot.ingestion.chunker import chunk_text

log = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


# ── helpers ──────────────────────────────────────────────────────────────────

async def _fetch_connector(conn, connector_id: int) -> dict | None:
    row = await conn.fetchrow(
        "SELECT * FROM connectors WHERE id=$1 AND is_active=TRUE", connector_id
    )
    return dict(row) if row else None


async def _existing_hashes(conn, connector_id: int) -> dict[str, tuple[int, str]]:
    """Return {external_id: (doc_id, content_hash)} for this connector."""
    rows = await conn.fetch(
        "SELECT id, external_id, content_hash FROM documents "
        "WHERE connector_id=$1 AND external_id IS NOT NULL",
        connector_id,
    )
    return {r["external_id"]: (r["id"], r["content_hash"] or "") for r in rows}


async def _upsert_document(conn, doc, connector_id: int, org_id: int, existing_doc_id: int | None) -> int:
    now = datetime.now(timezone.utc)
    meta = json.dumps({**doc.metadata, "connector_id": connector_id})

    if existing_doc_id:
        await conn.execute(
            """UPDATE documents SET title=$1, source=$2, metadata=$3,
               content_hash=$4, last_synced_at=$5
               WHERE id=$6""",
            doc.title, doc.source_url, meta, doc.content_hash, now, existing_doc_id,
        )
        # delete old chunks
        await conn.execute("DELETE FROM chunks WHERE doc_id=$1", existing_doc_id)
        doc_id = existing_doc_id
    else:
        doc_id = await conn.fetchval(
            """INSERT INTO documents (title, source, metadata, org_id, connector_id,
               external_id, content_hash, last_synced_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id""",
            doc.title, doc.source_url, meta, org_id, connector_id,
            doc.external_id, doc.content_hash, now,
        )

    chunks = chunk_text(doc.text)
    if chunks:
        embeddings = await embed_batch(chunks, task_type="RETRIEVAL_DOCUMENT")
        await conn.executemany(
            "INSERT INTO chunks (doc_id, chunk_index, text, embedding) VALUES ($1,$2,$3,$4)",
            [(doc_id, i, chunk, emb) for i, (chunk, emb) in enumerate(zip(chunks, embeddings))],
        )
    return doc_id


# ── core sync ─────────────────────────────────────────────────────────────────

async def run_sync(connector_id: int) -> dict:
    """
    Execute a full incremental sync for one connector.
    Returns {docs_added, docs_updated, docs_deleted, error}.
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await _fetch_connector(conn, connector_id)
        if not row:
            return {"error": f"Connector {connector_id} not found or inactive"}

        # Mark running + create job record
        job_id = await conn.fetchval(
            "INSERT INTO sync_jobs (connector_id, status) VALUES ($1,'running') RETURNING id",
            connector_id,
        )
        await conn.execute(
            "UPDATE connectors SET last_sync_status='running', updated_at=now() WHERE id=$1",
            connector_id,
        )

    # Import registry lazily to avoid circular imports at module load
    from rag_chatbot.connectors.registry import get as get_connector

    stats = {"docs_added": 0, "docs_updated": 0, "docs_deleted": 0, "error": None}

    try:
        config = json.loads(row["config"]) if isinstance(row["config"], str) else row["config"]
        connector = get_connector(row["connector_type"], config)

        async with pool.acquire() as conn:
            existing = await _existing_hashes(conn, connector_id)

        # Fetch and upsert changed documents
        async with pool.acquire() as conn:
            async for doc in connector.iter_changed({eid: h for eid, (_, h) in existing.items()}):
                prev = existing.get(doc.external_id)
                existing_doc_id = prev[0] if prev else None
                await _upsert_document(conn, doc, connector_id, row["org_id"], existing_doc_id)
                if existing_doc_id:
                    stats["docs_updated"] += 1
                else:
                    stats["docs_added"] += 1

        # Delete documents removed from the source
        deleted_ids = await connector.deleted_ids(
            {eid: h for eid, (_, h) in existing.items()}
        )
        if deleted_ids:
            async with pool.acquire() as conn:
                for eid in deleted_ids:
                    doc_id = existing[eid][0]
                    await conn.execute("DELETE FROM documents WHERE id=$1", doc_id)
                    stats["docs_deleted"] += 1

        # For ServiceNow connectors with incident ingestion enabled, run incident pipeline
        if (row["connector_type"] == "servicenow"
                and config.get("ingest_incidents", "").lower() == "true"):
            from rag_chatbot.connectors.incident_processor import process_incidents

            # Fetch org's LLM config for article generation
            llm_config: dict = {}
            async with pool.acquire() as conn:
                cfg_rows = await conn.fetch(
                    "SELECT key, value FROM app_config WHERE org_id=$1", row["org_id"]
                )
                for r in cfg_rows:
                    llm_config[r["key"]] = r["value"]

            inc_stats = await process_incidents(
                pool=pool,
                connector_id=connector_id,
                org_id=row["org_id"],
                config=config,
                llm_config=llm_config,
            )
            log.info(
                "Incident processing done for connector %d: %s", connector_id, inc_stats
            )
            if inc_stats.get("error") and not stats.get("error"):
                stats["error"] = f"incident_processor: {inc_stats['error']}"
            stats["incident_stats"] = inc_stats

        status = "success"
        inc = stats.get("incident_stats")
        incident_part = (
            f" | incidents: {inc['incidents_processed']} processed, "
            f"{inc['clusters_created']} articles created, "
            f"{inc['clusters_updated']} updated"
            if inc else ""
        )
        message = (
            f"✓ KB: +{stats['docs_added']} updated:{stats['docs_updated']} "
            f"deleted:{stats['docs_deleted']}{incident_part}"
        )
    except Exception as exc:
        log.exception("Sync failed for connector %d", connector_id)
        stats["error"] = str(exc)
        status = "error"
        message = str(exc)

    # Finalise job + connector status
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE sync_jobs SET status=$1, docs_added=$2, docs_updated=$3,
               docs_deleted=$4, error_message=$5, finished_at=now() WHERE id=$6""",
            status, stats["docs_added"], stats["docs_updated"],
            stats["docs_deleted"], stats.get("error"), job_id,
        )
        await conn.execute(
            """UPDATE connectors SET last_sync_status=$1, last_synced_at=now(),
               last_sync_message=$2, updated_at=now() WHERE id=$3""",
            status, message, connector_id,
        )

    return stats


# ── scheduler ────────────────────────────────────────────────────────────────

async def _scheduler_loop():
    """Every 60 s, find connectors due for sync and run them."""
    while True:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                due = await conn.fetch(
                    """SELECT id FROM connectors
                       WHERE is_active = TRUE
                         AND last_sync_status != 'running'
                         AND (
                             last_synced_at IS NULL
                             OR last_synced_at < now() - (sync_interval_minutes * INTERVAL '1 minute')
                         )"""
                )
            for row in due:
                asyncio.create_task(run_sync(row["id"]))
        except Exception:
            log.exception("Scheduler tick error")

        await asyncio.sleep(60)


def start_scheduler():
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    log.info("Connector sync scheduler started")


def stop_scheduler():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
