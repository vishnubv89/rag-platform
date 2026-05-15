"""
Langfuse v4 observability — shared client factory.

Usage:
    from rag_chatbot.observability import get_langfuse

    lf = get_langfuse()
    if lf:
        with lf.start_as_current_observation(name="my-span", type="SPAN") as obs:
            result = do_work()
            obs.update(input=..., output=result)

Returns None everywhere when LANGFUSE_SECRET_KEY is not set, so the backend
works identically with or without Langfuse configured.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_langfuse = None  # lazy singleton


def _enabled() -> bool:
    from rag_chatbot.config import settings
    return bool(settings.langfuse_secret_key)


def get_langfuse():
    """Return the shared Langfuse v4 client, or None if not configured."""
    if not _enabled():
        return None

    global _langfuse
    if _langfuse is None:
        try:
            from langfuse import Langfuse
            from rag_chatbot.config import settings
            _langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            log.info("Langfuse connected at %s", settings.langfuse_host)
        except Exception as exc:
            log.warning("Langfuse init failed: %s — tracing disabled", exc)
            return None

    return _langfuse
