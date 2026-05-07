import hashlib
from fastapi import Header, HTTPException, Request, status

import jwt

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


async def require_user(request: Request) -> dict:
    """Extract and validate Bearer token; return user dict."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = auth[7:]
    try:
        from rag_chatbot.auth.tokens import decode_access_token
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, name, role, org_id, is_active FROM users WHERE id=$1",
            int(payload["sub"]),
        )
    if not row or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return dict(row)
