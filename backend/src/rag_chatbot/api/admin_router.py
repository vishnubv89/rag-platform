"""
Admin API — all routes require X-Admin-Key header (verified via deps.verify_admin_key).

Groups:
  /admin/orgs         — org CRUD + api key management
  /admin/docs         — document management
  /admin/config       — per-org runtime settings
  /admin/analytics    — chat logs and token usage
  /admin/system       — health and migrations
"""
import hashlib
import os
import secrets
import time
from datetime import datetime, timezone
from rag_chatbot.api.audit import log_action

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from rag_chatbot.api.deps import verify_admin_key
from rag_chatbot.db.connection import get_pool, run_schema

Dep = Depends(verify_admin_key)

router = APIRouter(dependencies=[Dep])


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _resolve_org(org_id: int | None, conn) -> int:
    if org_id is None:
        row = await conn.fetchrow("SELECT id FROM organizations WHERE slug='default'")
        return row["id"]
    row = await conn.fetchrow("SELECT id FROM organizations WHERE id=$1", org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org_id


# ─────────────────────────────────────────────
# Orgs
# ─────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    slug: str

class OrgPatch(BaseModel):
    name: str | None = None
    is_active: bool | None = None


@router.get("/orgs")
async def list_orgs():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, slug, is_active, created_at FROM organizations ORDER BY id"
        )
    return [dict(r) for r in rows]


@router.post("/orgs", status_code=201)
async def create_org(body: OrgCreate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO organizations (name, slug) VALUES ($1, $2) RETURNING id, name, slug",
                body.name, body.slug,
            )
        except Exception:
            raise HTTPException(status_code=409, detail="Name or slug already exists")
    return dict(row)


@router.get("/orgs/{org_id}")
async def get_org(org_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        org = await conn.fetchrow(
            "SELECT id, name, slug, is_active, created_at FROM organizations WHERE id=$1", org_id
        )
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        config = await conn.fetch(
            "SELECT key, value FROM app_config WHERE org_id=$1 ORDER BY key", org_id
        )
    return {**dict(org), "config": {r["key"]: r["value"] for r in config}}


@router.patch("/orgs/{org_id}")
async def patch_org(org_id: int, body: OrgPatch):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if body.name is not None:
            await conn.execute(
                "UPDATE organizations SET name=$1, updated_at=now() WHERE id=$2", body.name, org_id
            )
        if body.is_active is not None:
            await conn.execute(
                "UPDATE organizations SET is_active=$1, updated_at=now() WHERE id=$2",
                body.is_active, org_id,
            )
        row = await conn.fetchrow(
            "SELECT id, name, slug, is_active FROM organizations WHERE id=$1", org_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")
    return dict(row)


@router.delete("/orgs/{org_id}", status_code=204)
async def delete_org(org_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE organizations SET is_active=FALSE, updated_at=now() WHERE id=$1", org_id
        )


# ─────────────────────────────────────────────
# API Keys
# ─────────────────────────────────────────────

class KeyCreate(BaseModel):
    label: str = ""


@router.get("/orgs/{org_id}/keys")
async def list_keys(org_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, label, is_active, last_used, created_at FROM api_keys WHERE org_id=$1 ORDER BY id",
            org_id,
        )
    return [dict(r) for r in rows]


@router.post("/orgs/{org_id}/keys", status_code=201)
async def create_key(org_id: int, body: KeyCreate):
    raw = "rag_" + secrets.token_urlsafe(32)
    key_hash = _sha256(raw)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO api_keys (org_id, key_hash, label) VALUES ($1,$2,$3) RETURNING id, label",
            org_id, key_hash, body.label,
        )
    return {**dict(row), "key": raw, "note": "This is the only time the raw key is shown."}


@router.delete("/orgs/{org_id}/keys/{key_id}", status_code=204)
async def revoke_key(org_id: int, key_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE api_keys SET is_active=FALSE WHERE id=$1 AND org_id=$2", key_id, org_id
        )


# ─────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────

import tempfile
from pathlib import Path as FPath
from rag_chatbot.ingestion.pipeline import ingest_text, ingest_file


@router.get("/docs")
async def list_docs(
    org_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    offset = (page - 1) * limit
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            """
            SELECT d.id, d.title, d.source, d.created_at, d.metadata,
                   COUNT(c.id) AS chunk_count
            FROM   documents d
            LEFT JOIN chunks c ON c.doc_id = d.id
            WHERE  d.org_id = $1
            GROUP  BY d.id
            ORDER  BY d.id DESC
            LIMIT  $2 OFFSET $3
            """,
            oid, limit, offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM documents WHERE org_id=$1", oid)

    def _row(r):
        d = dict(r)
        meta = d.get("metadata") or {}
        if isinstance(meta, str):
            import json as _json
            try:
                meta = _json.loads(meta)
            except Exception:
                meta = {}
        d["doc_source"] = meta.get("source", "")
        d["cluster_key"] = meta.get("cluster_key", "")
        return d

    return {"total": total, "page": page, "limit": limit, "items": [_row(r) for r in rows]}


@router.get("/docs/search")
async def search_docs(
    q: str = Query(..., min_length=1),
    org_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            """
            SELECT d.id, d.title, d.source, d.created_at,
                   COUNT(c.id) AS chunk_count
            FROM   documents d
            LEFT JOIN chunks c ON c.doc_id = d.id
            WHERE  d.org_id = $1
              AND  (d.title ILIKE $2
                    OR EXISTS (
                        SELECT 1 FROM chunks c2
                        WHERE c2.doc_id = d.id
                          AND c2.search_vec @@ plainto_tsquery('english', $3)
                    ))
            GROUP  BY d.id
            ORDER  BY d.id DESC
            LIMIT  $4
            """,
            oid, f"%{q}%", q, limit,
        )
    return {"items": [dict(r) for r in rows]}


@router.get("/docs/{doc_id}")
async def get_doc(doc_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        doc = await conn.fetchrow(
            "SELECT id, title, source, org_id, metadata, created_at FROM documents WHERE id=$1", doc_id
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        chunks = await conn.fetch(
            "SELECT id, chunk_index, text FROM chunks WHERE doc_id=$1 ORDER BY chunk_index",
            doc_id,
        )
    return {**dict(doc), "chunks": [dict(c) for c in chunks]}


@router.delete("/docs/{doc_id}", status_code=204)
async def delete_doc(doc_id: int, org_id: int | None = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        deleted = await conn.execute(
            "DELETE FROM documents WHERE id=$1 AND org_id=$2", doc_id, oid
        )
        if deleted == "DELETE 0":
            raise HTTPException(status_code=404, detail="Document not found in this org")
    await log_action(org_id=oid, user_id=None, action="delete", resource="document", resource_id=doc_id)


class TextIngestBody(BaseModel):
    title: str
    text: str
    source: str = ""
    org_id: int | None = None


@router.post("/docs/ingest/text", status_code=201)
async def admin_ingest_text(body: TextIngestBody):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(body.org_id, conn)
    result = await ingest_text(text=body.text, title=body.title, source=body.source, org_id=oid)
    return result


@router.post("/docs/ingest/file", status_code=201)
async def admin_ingest_file(
    file: UploadFile = File(...),
    org_id: int | None = Query(None),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
    suffix = FPath(file.filename or "upload").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = await ingest_file(tmp_path, title=file.filename, org_id=oid)
    finally:
        FPath(tmp_path).unlink(missing_ok=True)
    return result


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    org_id: int | None = None
    settings: dict[str, str]


@router.get("/config")
async def get_config(org_id: int | None = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            "SELECT key, value, updated_at FROM app_config WHERE org_id=$1 ORDER BY key", oid
        )
    return {"org_id": oid, "config": {r["key"]: r["value"] for r in rows}}


@router.put("/config")
async def update_config(body: ConfigUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(body.org_id, conn)
        for key, value in body.settings.items():
            await conn.execute(
                """
                INSERT INTO app_config (org_id, key, value)
                VALUES ($1, $2, $3)
                ON CONFLICT (org_id, key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()
                """,
                oid, key, value,
            )
    return {"org_id": oid, "updated": list(body.settings.keys())}


@router.get("/config/{key}")
async def get_config_key(key: str, org_id: int | None = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        row = await conn.fetchrow(
            "SELECT value, updated_at FROM app_config WHERE org_id=$1 AND key=$2", oid, key
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Config key '{key}' not found")
    return {"org_id": oid, "key": key, **dict(row)}


# ─────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────

@router.get("/analytics/summary")
async def analytics_summary(
    org_id: int | None = Query(None),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        where = "org_id=$1"
        params: list = [oid]
        if from_dt:
            params.append(from_dt)
            where += f" AND created_at >= ${len(params)}"
        if to_dt:
            params.append(to_dt)
            where += f" AND created_at <= ${len(params)}"
        row = await conn.fetchrow(
            f"""
            SELECT COUNT(*)                             AS total_chats,
                   COALESCE(AVG(latency_ms),0)::INT    AS avg_latency_ms,
                   COUNT(*) FILTER (WHERE feedback = 1)  AS thumbs_up,
                   COUNT(*) FILTER (WHERE feedback = -1) AS thumbs_down
            FROM chat_logs WHERE {where}
            """,
            *params,
        )
    return dict(row)


@router.get("/analytics/logs")
async def analytics_logs(
    org_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    from_dt: str | None = Query(None),
    to_dt: str | None = Query(None),
):
    offset = (page - 1) * limit
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        where = "org_id=$1"
        params: list = [oid]
        if from_dt:
            params.append(from_dt)
            where += f" AND created_at >= ${len(params)}"
        if to_dt:
            params.append(to_dt)
            where += f" AND created_at <= ${len(params)}"
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"""
            SELECT id, session_id, LEFT(user_message,100) AS user_message,
                   LEFT(assistant_response,100) AS assistant_response,
                   loop_count, latency_ms, created_at
            FROM   chat_logs WHERE {where}
            ORDER  BY created_at DESC
            LIMIT  ${len(params)-1} OFFSET ${len(params)}
            """,
            *params,
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM chat_logs WHERE {where}", *params[:-2])
    return {"total": total, "page": page, "items": [dict(r) for r in rows]}


@router.get("/analytics/logs/{log_id}")
async def get_log(log_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM chat_logs WHERE id=$1", log_id)
    if not row:
        raise HTTPException(status_code=404, detail="Log not found")
    return dict(row)


@router.get("/analytics/token-usage")
async def token_usage(
    org_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            """
            SELECT DATE(created_at) AS day,
                   COUNT(*)::INT               AS chats,
                   COALESCE(AVG(latency_ms),0)::INT AS avg_latency_ms
            FROM   chat_logs
            WHERE  org_id=$1 AND created_at >= now() - ($2 || ' days')::INTERVAL
            GROUP  BY DATE(created_at)
            ORDER  BY day
            """,
            oid, str(days),
        )
    return [dict(r) for r in rows]


@router.get("/analytics/top-sources")
async def top_sources(
    org_id: int | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=365),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            """
            SELECT d.id, d.title, COUNT(*) AS citation_count
            FROM   chat_logs cl
            JOIN   LATERAL unnest(cl.source_chunk_ids) AS cid ON TRUE
            JOIN   chunks c ON c.id = cid
            JOIN   documents d ON d.id = c.doc_id
            WHERE  cl.org_id=$1
              AND  cl.created_at >= now() - ($2 || ' days')::INTERVAL
            GROUP  BY d.id, d.title
            ORDER  BY citation_count DESC
            LIMIT  $3
            """,
            oid, str(days), limit,
        )
    return [dict(r) for r in rows]


@router.get("/analytics/topic-graph")
async def topic_graph(
    org_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        # Citation count per document → node size
        node_rows = await conn.fetch(
            """
            SELECT d.id, d.title, d.source, COUNT(*) AS citations
            FROM   chat_logs cl
            JOIN   LATERAL unnest(cl.source_chunk_ids) AS cid ON TRUE
            JOIN   chunks c ON c.id = cid
            JOIN   documents d ON d.id = c.doc_id
            WHERE  cl.org_id=$1
              AND  cl.created_at >= now() - ($2 || ' days')::INTERVAL
            GROUP  BY d.id, d.title, d.source
            """,
            oid, str(days),
        )
        # Co-citation count between document pairs → edge weight
        edge_rows = await conn.fetch(
            """
            WITH doc_per_log AS (
                SELECT cl.id AS log_id, d.id AS doc_id
                FROM   chat_logs cl
                JOIN   LATERAL unnest(cl.source_chunk_ids) AS cid ON TRUE
                JOIN   chunks c ON c.id = cid
                JOIN   documents d ON d.id = c.doc_id
                WHERE  cl.org_id=$1
                  AND  cl.created_at >= now() - ($2 || ' days')::INTERVAL
                GROUP  BY cl.id, d.id
            )
            SELECT a.doc_id AS source, b.doc_id AS target, COUNT(*) AS weight
            FROM   doc_per_log a
            JOIN   doc_per_log b ON a.log_id = b.log_id AND a.doc_id < b.doc_id
            GROUP  BY a.doc_id, b.doc_id
            HAVING COUNT(*) >= 1
            """,
            oid, str(days),
        )
    return {
        "nodes": [dict(r) for r in node_rows],
        "edges": [dict(r) for r in edge_rows],
    }


# ─────────────────────────────────────────────
# System
# ─────────────────────────────────────────────

@router.get("/system/health")
async def system_health():
    pool = await get_pool()
    async with pool.acquire() as conn:
        pg_version = await conn.fetchval("SELECT version()")
        pool_size = pool.get_size()
    return {
        "status": "ok",
        "postgres": pg_version,
        "pool_size": pool_size,
        "app_env": __import__("rag_chatbot.config", fromlist=["settings"]).settings.app_env,
    }


@router.post("/system/schema/migrate", status_code=200)
async def run_migrations():
    await run_schema()
    return {"status": "migrations applied"}


# ─────────────────────────────────────────────
# Connectors
# ─────────────────────────────────────────────

class ConnectorCreate(BaseModel):
    name: str
    connector_type: str
    config: dict = {}
    sync_interval_minutes: int = 60
    org_id: int | None = None


class ConnectorPatch(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None
    sync_interval_minutes: int | None = None


@router.get("/connectors")
async def list_connectors(org_id: int | None = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            """SELECT id, name, connector_type, is_active, sync_interval_minutes,
                      last_synced_at, last_sync_status, last_sync_message, created_at
               FROM connectors WHERE org_id=$1 ORDER BY id""",
            oid,
        )
    return [dict(r) for r in rows]


@router.post("/connectors", status_code=201)
async def create_connector(body: ConnectorCreate):
    from rag_chatbot.connectors.registry import get as get_connector, available_types
    if body.connector_type not in available_types():
        raise HTTPException(status_code=400, detail=f"Unknown connector type. Available: {available_types()}")

    # Validate credentials
    connector = get_connector(body.connector_type, body.config)
    ok, err = await connector.validate_config()
    if not ok:
        raise HTTPException(status_code=422, detail=f"Config validation failed: {err}")

    pool = await get_pool()
    import json as _json
    async with pool.acquire() as conn:
        oid = await _resolve_org(body.org_id, conn)
        row = await conn.fetchrow(
            """INSERT INTO connectors (org_id, name, connector_type, config, sync_interval_minutes)
               VALUES ($1,$2,$3,$4,$5)
               RETURNING id, name, connector_type, is_active, sync_interval_minutes, last_sync_status""",
            oid, body.name, body.connector_type,
            _json.dumps(body.config), body.sync_interval_minutes,
        )
    return dict(row)


@router.get("/connectors/types")
async def connector_types():
    from rag_chatbot.connectors.registry import available_types
    return {"types": available_types()}


@router.get("/connectors/{connector_id}")
async def get_connector_detail(connector_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, name, connector_type, is_active, sync_interval_minutes,
                      last_synced_at, last_sync_status, last_sync_message, created_at, org_id
               FROM connectors WHERE id=$1""",
            connector_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Connector not found")
        jobs = await conn.fetch(
            """SELECT id, status, docs_added, docs_updated, docs_deleted,
                      error_message, started_at, finished_at
               FROM sync_jobs WHERE connector_id=$1 ORDER BY started_at DESC LIMIT 10""",
            connector_id,
        )
    return {**dict(row), "recent_jobs": [dict(j) for j in jobs]}


@router.patch("/connectors/{connector_id}")
async def patch_connector(connector_id: int, body: ConnectorPatch, org_id: int | None = Query(None)):
    pool = await get_pool()
    import json as _json
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        row = await conn.fetchrow("SELECT * FROM connectors WHERE id=$1 AND org_id=$2", connector_id, oid)
        if not row:
            raise HTTPException(status_code=404, detail="Connector not found in this org")
        if body.name is not None:
            await conn.execute("UPDATE connectors SET name=$1, updated_at=now() WHERE id=$2", body.name, connector_id)
        if body.config is not None:
            await conn.execute("UPDATE connectors SET config=$1, updated_at=now() WHERE id=$2", _json.dumps(body.config), connector_id)
        if body.is_active is not None:
            await conn.execute("UPDATE connectors SET is_active=$1, updated_at=now() WHERE id=$2", body.is_active, connector_id)
        if body.sync_interval_minutes is not None:
            await conn.execute("UPDATE connectors SET sync_interval_minutes=$1, updated_at=now() WHERE id=$2", body.sync_interval_minutes, connector_id)
        updated = await conn.fetchrow(
            "SELECT id, name, connector_type, is_active, sync_interval_minutes, last_sync_status FROM connectors WHERE id=$1",
            connector_id,
        )
    return dict(updated)


@router.delete("/connectors/{connector_id}", status_code=204)
async def delete_connector(connector_id: int, org_id: int | None = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        deleted = await conn.execute(
            "DELETE FROM connectors WHERE id=$1 AND org_id=$2", connector_id, oid
        )
        if deleted == "DELETE 0":
            raise HTTPException(status_code=404, detail="Connector not found in this org")
    await log_action(org_id=oid, user_id=None, action="delete", resource="connector", resource_id=connector_id)


@router.post("/connectors/{connector_id}/sync")
async def trigger_sync(connector_id: int):
    import asyncio
    from rag_chatbot.connectors.sync_engine import run_sync
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT org_id FROM connectors WHERE id=$1", connector_id)
    asyncio.create_task(run_sync(connector_id))
    await log_action(org_id=row["org_id"] if row else None, user_id=None, action="sync", resource="connector", resource_id=connector_id)
    return {"status": "sync triggered", "connector_id": connector_id}


@router.get("/connectors/{connector_id}/jobs")
async def connector_jobs(connector_id: int, limit: int = Query(20, ge=1, le=100)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, status, docs_added, docs_updated, docs_deleted,
                      error_message, started_at, finished_at
               FROM sync_jobs WHERE connector_id=$1 ORDER BY started_at DESC LIMIT $2""",
            connector_id, limit,
        )
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# Knowledge Health
# ─────────────────────────────────────────────

@router.get("/knowledge/health")
async def knowledge_health(org_id: int | None = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        row = await conn.fetchrow("SELECT * FROM knowledge_health WHERE org_id=$1", oid)
    return dict(row) if row else {
        "org_id": oid, "total_docs": 0, "total_chunks": 0,
        "stale_docs": 0, "open_conflicts": 0, "active_connectors": 0, "freshness_pct": 100,
    }


@router.get("/knowledge/conflicts")
async def list_conflicts(
    org_id: int | None = Query(None),
    status: str = Query("pending"),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            """SELECT kc.id, kc.topic, kc.conflict_summary, kc.status, kc.created_at,
                      ca.text AS text_a, cb.text AS text_b,
                      da.title AS doc_title_a, db.title AS doc_title_b
               FROM knowledge_conflicts kc
               JOIN chunks ca ON ca.id = kc.chunk_id_a
               JOIN chunks cb ON cb.id = kc.chunk_id_b
               JOIN documents da ON da.id = ca.doc_id
               JOIN documents db ON db.id = cb.doc_id
               WHERE kc.org_id=$1 AND kc.status=$2
               ORDER BY kc.created_at DESC""",
            oid, status,
        )
    return [dict(r) for r in rows]


class ConflictResolve(BaseModel):
    status: str  # resolved | dismissed
    resolved_doc_id: int | None = None


@router.patch("/knowledge/conflicts/{conflict_id}")
async def resolve_conflict(conflict_id: int, body: ConflictResolve, org_id: int | None = Query(None)):
    if body.status not in ("resolved", "dismissed"):
        raise HTTPException(status_code=400, detail="status must be 'resolved' or 'dismissed'")
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        updated = await conn.execute(
            """UPDATE knowledge_conflicts
               SET status=$1, resolved_doc_id=$2, resolved_at=now()
               WHERE id=$3 AND org_id=$4""",
            body.status, body.resolved_doc_id, conflict_id, oid,
        )
        if updated == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Conflict not found in this org")
    return {"id": conflict_id, "status": body.status}


@router.get("/knowledge/stale")
async def stale_documents(
    org_id: int | None = Query(None),
    days: int = Query(90, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn)
        rows = await conn.fetch(
            """SELECT d.id, d.title, d.source, d.last_synced_at, d.created_at,
                      c.name AS connector_name
               FROM documents d
               LEFT JOIN connectors c ON c.id = d.connector_id
               WHERE d.org_id=$1
                 AND (d.last_synced_at < now() - ($2 || ' days')::INTERVAL
                      OR d.last_synced_at IS NULL)
               ORDER BY d.last_synced_at ASC NULLS FIRST
               LIMIT $3""",
            oid, str(days), limit,
        )
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "member"
    org_id: int | None = None

class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    org_id: int | None = None
    is_active: bool | None = None
    password: str | None = None


@router.get("/users")
async def list_users(org_id: int | None = Query(None)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if org_id is not None:
            rows = await conn.fetch(
                """SELECT u.id, u.email, u.name, u.role, u.org_id, u.is_active,
                          u.created_at, u.last_login_at, o.name AS org_name
                   FROM users u LEFT JOIN organizations o ON o.id = u.org_id
                   WHERE u.org_id=$1 ORDER BY u.created_at DESC""", org_id
            )
        else:
            rows = await conn.fetch(
                """SELECT u.id, u.email, u.name, u.role, u.org_id, u.is_active,
                          u.created_at, u.last_login_at, o.name AS org_name
                   FROM users u LEFT JOIN organizations o ON o.id = u.org_id
                   ORDER BY u.created_at DESC"""
            )
    return [dict(r) for r in rows]


@router.post("/users", status_code=201)
async def create_user(body: UserCreate):
    from rag_chatbot.auth.password import hash_password
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval("SELECT id FROM users WHERE email=$1", body.email)
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
        user_id = await conn.fetchval(
            """INSERT INTO users (email, name, password_hash, role, org_id)
               VALUES ($1,$2,$3,$4,$5) RETURNING id""",
            body.email, body.name, hash_password(body.password), body.role, body.org_id,
        )
    await log_action(org_id=body.org_id, user_id=None, action="create", resource="user",
                     resource_id=user_id, detail={"email": body.email, "role": body.role})
    return {"id": user_id, "email": body.email}


@router.patch("/users/{user_id}")
async def update_user(user_id: int, body: UserPatch):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE id=$1", user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if body.name is not None:
            await conn.execute("UPDATE users SET name=$1 WHERE id=$2", body.name, user_id)
        if body.role is not None:
            await conn.execute("UPDATE users SET role=$1 WHERE id=$2", body.role, user_id)
        if body.org_id is not None:
            await conn.execute("UPDATE users SET org_id=$1 WHERE id=$2", body.org_id, user_id)
        if body.is_active is not None:
            await conn.execute("UPDATE users SET is_active=$1 WHERE id=$2", body.is_active, user_id)
        if body.password is not None:
            from rag_chatbot.auth.password import hash_password
            await conn.execute("UPDATE users SET password_hash=$1 WHERE id=$2",
                               hash_password(body.password), user_id)
    return {"id": user_id}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT org_id, email FROM users WHERE id=$1", user_id)
        await conn.execute("DELETE FROM users WHERE id=$1", user_id)
    await log_action(org_id=row["org_id"] if row else None, user_id=None, action="delete",
                     resource="user", resource_id=user_id, detail={"email": row["email"] if row else ""})

# ─────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────

@router.get("/audit")
async def list_audit(
    org_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        oid = await _resolve_org(org_id, conn) if org_id else None
        where = "WHERE a.org_id=$1" if oid else ""
        args = [oid] if oid else []
        rows = await conn.fetch(
            f"""
            SELECT a.id, a.org_id, a.user_id, u.email AS user_email,
                   a.action, a.resource, a.resource_id, a.detail, a.ip,
                   a.created_at
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            {where}
            ORDER BY a.created_at DESC
            LIMIT {limit} OFFSET {offset}
            """,
            *args,
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM audit_logs a {where}", *args
        )
    return {
        "total": total,
        "items": [
            {**dict(r), "detail": r["detail"] or {}, "created_at": str(r["created_at"])}
            for r in rows
        ],
    }
