from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

import jwt

from rag_chatbot.config import settings

_ALGORITHM = "HS256"


@dataclass
class TokenPair:
    access_token: str
    token_type: str = "bearer"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, role: str, org_id: int | None) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "org_id": org_id,
        "exp": _now() + timedelta(minutes=settings.jwt_access_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": _now() + timedelta(days=settings.jwt_refresh_expire_days),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


def decode_refresh_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("not a refresh token")
    return int(payload["sub"])
