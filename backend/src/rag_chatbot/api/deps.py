import hashlib
from fastapi import Header, HTTPException, status

from rag_chatbot.config import settings
from rag_chatbot.db.connection import get_pool


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def verify_admin_key(x_admin_key: str = Header(...)) -> str:
    """Accept the request if the key matches the bootstrap secret or a live api_keys row."""
    if x_admin_key == settings.admin_secret_key:
        return x_admin_key

    key_hash = _sha256(x_admin_key)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM api_keys WHERE key_hash = $1 AND is_active = TRUE",
            key_hash,
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked admin key",
            )
        await conn.execute(
            "UPDATE api_keys SET last_used = now() WHERE id = $1", row["id"]
        )
    return x_admin_key
