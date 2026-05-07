"""Async httpx client that proxies all calls to the backend admin API."""
import httpx
from admin_ui.config import settings

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.backend_url,
            headers={"X-Admin-Key": settings.admin_secret_key},
            timeout=30.0,
        )
    return _client


def _raise(r: httpx.Response) -> None:
    """Raise with the backend's detail message instead of the raw HTTP error."""
    if r.is_error:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text or r.reason_phrase
        raise Exception(detail)


async def _get(path: str, **params) -> dict | list:
    r = await get_client().get(path, params={k: v for k, v in params.items() if v is not None})
    _raise(r)
    return r.json()


async def _post(path: str, json: dict | None = None, **kwargs) -> dict:
    r = await get_client().post(path, json=json, **kwargs)
    _raise(r)
    try:
        return r.json()
    except Exception:
        return {}


async def _put(path: str, json: dict) -> dict:
    r = await get_client().put(path, json=json)
    _raise(r)
    return r.json()


async def _patch(path: str, json: dict, **params) -> dict:
    r = await get_client().patch(path, json=json, params={k: v for k, v in params.items() if v is not None})
    _raise(r)
    try:
        return r.json()
    except Exception:
        return {}


async def _delete(path: str, **params) -> None:
    r = await get_client().delete(path, params={k: v for k, v in params.items() if v is not None})
    _raise(r)


# ── Orgs ──────────────────────────────────────────────────────────────────────

async def list_orgs() -> list:
    return await _get("/admin/orgs")

async def create_org(name: str, slug: str) -> dict:
    return await _post("/admin/orgs", json={"name": name, "slug": slug})

async def get_org(org_id: int) -> dict:
    return await _get(f"/admin/orgs/{org_id}")

async def patch_org(org_id: int, **fields) -> dict:
    return await _patch(f"/admin/orgs/{org_id}", json=fields)

async def delete_org(org_id: int) -> None:
    await _delete(f"/admin/orgs/{org_id}")


# ── API Keys ───────────────────────────────────────────────────────────────────

async def list_keys(org_id: int) -> list:
    return await _get(f"/admin/orgs/{org_id}/keys")

async def create_key(org_id: int, label: str) -> dict:
    return await _post(f"/admin/orgs/{org_id}/keys", json={"label": label})

async def revoke_key(org_id: int, key_id: int) -> None:
    await _delete(f"/admin/orgs/{org_id}/keys/{key_id}")


# ── Documents ─────────────────────────────────────────────────────────────────

async def list_docs(org_id: int | None = None, page: int = 1, limit: int = 20) -> dict:
    return await _get("/admin/docs", org_id=org_id, page=page, limit=limit)

async def get_doc(doc_id: int) -> dict:
    return await _get(f"/admin/docs/{doc_id}")

async def delete_doc(doc_id: int, org_id: int | None = None) -> None:
    await _delete(f"/admin/docs/{doc_id}", org_id=org_id)

async def ingest_text(title: str, text: str, source: str, org_id: int | None) -> dict:
    return await _post(
        "/admin/docs/ingest/text",
        json={"title": title, "text": text, "source": source, "org_id": org_id},
    )


# ── Config ────────────────────────────────────────────────────────────────────

async def get_config(org_id: int | None = None) -> dict:
    return await _get("/admin/config", org_id=org_id)

async def update_config(org_id: int | None, cfg: dict) -> dict:
    return await _put("/admin/config", json={"org_id": org_id, "settings": cfg})


# ── Analytics ─────────────────────────────────────────────────────────────────

async def analytics_summary(org_id: int | None = None, from_dt: str | None = None, to_dt: str | None = None) -> dict:
    return await _get("/admin/analytics/summary", org_id=org_id, from_dt=from_dt, to_dt=to_dt)

async def list_logs(org_id: int | None = None, page: int = 1, from_dt: str | None = None, to_dt: str | None = None) -> dict:
    return await _get("/admin/analytics/logs", org_id=org_id, page=page, from_dt=from_dt, to_dt=to_dt)

async def token_usage(org_id: int | None = None, days: int = 30) -> list:
    return await _get("/admin/analytics/token-usage", org_id=org_id, days=days)


# ── Connectors ────────────────────────────────────────────────────────────────

async def list_connectors(org_id: int | None = None) -> list:
    return await _get("/admin/connectors", org_id=org_id)

async def connector_types() -> list:
    data = await _get("/admin/connectors/types")
    return data.get("types", [])

async def create_connector(name: str, connector_type: str, config: dict, sync_interval_minutes: int, org_id: int | None) -> dict:
    return await _post("/admin/connectors", json={
        "name": name, "connector_type": connector_type,
        "config": config, "sync_interval_minutes": sync_interval_minutes,
        "org_id": org_id,
    })

async def get_connector(connector_id: int) -> dict:
    return await _get(f"/admin/connectors/{connector_id}")

async def patch_connector(connector_id: int, org_id: int | None = None, **fields) -> dict:
    return await _patch(f"/admin/connectors/{connector_id}", json=fields, org_id=org_id)

async def delete_connector(connector_id: int, org_id: int | None = None) -> None:
    await _delete(f"/admin/connectors/{connector_id}", org_id=org_id)

async def trigger_sync(connector_id: int) -> dict:
    return await _post(f"/admin/connectors/{connector_id}/sync")

async def connector_jobs(connector_id: int) -> list:
    return await _get(f"/admin/connectors/{connector_id}/jobs")


# ── Knowledge Health ──────────────────────────────────────────────────────────

async def knowledge_health(org_id: int | None = None) -> dict:
    return await _get("/admin/knowledge/health", org_id=org_id)

async def list_conflicts(org_id: int | None = None, status: str = "pending") -> list:
    return await _get("/admin/knowledge/conflicts", org_id=org_id, status=status)

async def resolve_conflict(conflict_id: int, status: str, resolved_doc_id: int | None = None) -> dict:
    return await _patch(f"/admin/knowledge/conflicts/{conflict_id}", json={"status": status, "resolved_doc_id": resolved_doc_id})

async def stale_documents(org_id: int | None = None, days: int = 90) -> list:
    return await _get("/admin/knowledge/stale", org_id=org_id, days=days)
