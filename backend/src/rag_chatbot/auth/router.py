"""
Auth endpoints:
  POST /auth/setup   — first-run: create superadmin (only if no users exist)
  POST /auth/login   — email + password → access token + refresh cookie
  POST /auth/refresh — refresh cookie → new access token
  POST /auth/logout  — clear refresh cookie
  GET  /auth/me      — current user info
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr

import jwt

from rag_chatbot.auth.password import hash_password, verify_password
from rag_chatbot.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from rag_chatbot.db.connection import get_pool

router = APIRouter()

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds


# ── helpers ───────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=False,        # set True when behind HTTPS in production
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/auth/refresh",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path="/auth/refresh")


async def _get_user_by_id(conn, user_id: int) -> dict | None:
    row = await conn.fetchrow(
        "SELECT id, email, name, role, org_id, is_active FROM users WHERE id=$1",
        user_id,
    )
    return dict(row) if row else None


# ── schemas ───────────────────────────────────────────────────────────────────

class SetupRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    org_id: int | None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/setup", response_model=TokenResponse, status_code=201)
async def setup(body: SetupRequest, response: Response):
    """Create the first superadmin. Returns 409 if any user already exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Setup already completed. Use /auth/login.",
            )
        user_id = await conn.fetchval(
            """INSERT INTO users (email, name, password_hash, role)
               VALUES ($1, $2, $3, 'superadmin') RETURNING id""",
            body.email, body.name, hash_password(body.password),
        )

    access = create_access_token(user_id, "superadmin", None)
    refresh = create_refresh_token(user_id)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash, role, org_id, is_active FROM users WHERE email=$1",
            body.email,
        )

    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET last_login_at=now() WHERE id=$1", row["id"])

    access = create_access_token(row["id"], row["role"], row["org_id"])
    refresh = create_refresh_token(row["id"])
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get(_REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        user_id = decode_refresh_token(token)
    except jwt.ExpiredSignatureError:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await _get_user_by_id(conn, user_id)

    if not user or not user["is_active"]:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access = create_access_token(user["id"], user["role"], user["org_id"])
    new_refresh = create_refresh_token(user["id"])
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access)


@router.post("/logout")
async def logout(response: Response):
    _clear_refresh_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(request: Request):
    from rag_chatbot.api.deps import require_user
    user = await require_user(request)
    return UserResponse(**user)
