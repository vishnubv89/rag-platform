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
            SELECT d.id, d.title, d.source, d.created_at,
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
    return {"total": total, "page": page, "limit": limit, "items": [dict(r) for r in rows]}


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
            "SELECT id, chunk_index, LEFT(text,200) AS preview FROM chunks WHERE doc_id=$1 ORDER BY chunk_index LIMIT 20",
            doc_id,
        )
    return {**dict(doc), "chunks_preview": [dict(c) for c in chunks]}


@router.delete("/docs/{doc_id}", status_code=204)
async def delete_doc(doc_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM documents WHERE id=$1", doc_id)


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
            SELECT COUNT(*) AS total_chats,
                   COALESCE(SUM(prompt_tokens),0) AS total_prompt_tokens,
                   COALESCE(SUM(completion_tokens),0) AS total_completion_tokens,
                   COALESCE(AVG(latency_ms),0)::INT AS avg_latency_ms
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
                   loop_count, prompt_tokens, completion_tokens, latency_ms, created_at
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
                   SUM(prompt_tokens)::INT     AS prompt_tokens,
                   SUM(completion_tokens)::INT AS completion_tokens,
                   COUNT(*)::INT               AS chats
            FROM   chat_logs
            WHERE  org_id=$1 AND created_at >= now() - ($2 || ' days')::INTERVAL
            GROUP  BY DATE(created_at)
            ORDER  BY day
            """,
            oid, str(days),
        )
    return [dict(r) for r in rows]


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
    migration_path = (
        FPath(__file__).parent.parent / "db" / "migrations" / "001_multitenancy.sql"
    )
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(migration_path.read_text())
    return {"status": "migrations applied"}
