import json
from fastapi import Request
from rag_chatbot.db.connection import get_pool


async def log_action(
    *,
    request: Request | None = None,
    org_id: int | None,
    user_id: int | None,
    action: str,
    resource: str,
    resource_id: str | int | None = None,
    detail: dict | None = None,
) -> None:
    ip = None
    if request is not None:
        ip = request.client.host if request.client else None

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_logs (org_id, user_id, action, resource, resource_id, detail, ip)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            """,
            org_id,
            user_id,
            action,
            resource,
            str(resource_id) if resource_id is not None else None,
            json.dumps(detail or {}),
            ip,
        )
