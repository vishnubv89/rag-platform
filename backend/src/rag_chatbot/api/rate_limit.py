from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from rag_chatbot.api.deps import _decode_bearer


def _key_by_user(request: Request) -> str:
    """Rate-limit key: user ID from JWT, fallback to IP."""
    try:
        payload = _decode_bearer(request)
        return f"user:{payload['sub']}"
    except Exception:
        return get_remote_address(request)


limiter = Limiter(key_func=_key_by_user, default_limits=[])


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Try again shortly."},
    )
