import hashlib
import logging

from fastapi import Header, HTTPException, Request, status

import jwt

from rag_chatbot.config import settings
from rag_chatbot.db.connection import get_pool

_log = logging.getLogger(__name__)


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


def _decode_bearer(request: Request) -> dict:
    """Decode Bearer token from request headers synchronously (no DB lookup)."""
    from rag_chatbot.auth.tokens import decode_access_token
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ValueError("No bearer token")
    return decode_access_token(auth[7:])


def extract_zitadel_token(request: Request) -> str | None:
    """
    Return the raw Bearer token only when it is a Zitadel RS256 JWT.
    Returns None for local HS256 tokens or when no Authorization header exists.

    Used by chat endpoints to attach the Zitadel token to AgentState so the
    retriever can perform OBO token exchange with ServiceNow.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    raw = auth[7:]
    try:
        header = jwt.get_unverified_header(raw)
        # Local tokens use HS256; Zitadel issues RS256
        if header.get("alg") == "RS256":
            return raw
    except jwt.DecodeError:
        pass
    return None


async def require_user(request: Request) -> dict:
    """
    Extract and validate a Bearer token; return a user dict.

    Validation order
    ----------------
    1. Local HS256 JWT (email+password login) — fast, no network call.
    2. Zitadel RS256 OIDC JWT — only attempted when ZITADEL_ISSUER is set
       and the local decode fails.  OIDC users are not looked up in the local
       users table; their profile comes from the token claims.

    The returned dict always contains: id, email, name, role, org_id, is_active.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = auth[7:]

    # --- 1. Try local HS256 ---
    try:
        from rag_chatbot.auth.tokens import decode_access_token
        payload = decode_access_token(token)
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, name, role, org_id, is_active FROM users WHERE id=$1",
                int(payload["sub"]),
            )
        if not row or not row["is_active"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return dict(row)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        pass  # fall through to OIDC

    # --- 2. Try Zitadel OIDC (RS256) ---
    from rag_chatbot.auth.oidc import oidc_enabled, validate_oidc_token
    if not oidc_enabled():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        return await validate_oidc_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        # Log the unverified claims so we can see iss/aud without a round-trip
        try:
            unverified = jwt.decode(token, options={"verify_signature": False, "verify_aud": False, "verify_iss": False})
            _log.error("OIDC validation failed: %s | unverified claims: iss=%s aud=%s sub=%s",
                       exc, unverified.get("iss"), unverified.get("aud"), unverified.get("sub"))
        except Exception:
            _log.error("OIDC validation failed: %s | could not decode token", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


# ---------------------------------------------------------------------------
# Role-based access control dependencies
# ---------------------------------------------------------------------------

async def require_admin(request: Request) -> dict:
    """Allow only users with role 'admin' or 'superadmin'."""
    user = await require_user(request)
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_superadmin(request: Request) -> dict:
    """Allow only users with role 'superadmin' (cross-org operations)."""
    user = await require_user(request)
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return user


def assert_org_access(user: dict, org_id: int) -> None:
    """
    Raise 403 if the user does not belong to the requested org.
    Superadmins bypass this check (they can access all orgs).
    """
    if user.get("role") == "superadmin":
        return
    user_org = user.get("org_id")
    if user_org is None or user_org != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access to org {org_id} denied",
        )
