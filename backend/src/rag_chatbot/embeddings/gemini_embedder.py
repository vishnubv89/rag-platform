import asyncio
import functools
import time

from google import genai
from google.genai import types

from rag_chatbot.config import settings

_client: genai.Client | None = None

_BATCH_SIZE  = 100   # Gemini hard limit per embed_content call
_MAX_RETRIES = 4
_INTER_DELAY = 4.1   # seconds between embedding calls — keeps us under 15 RPM free tier


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


@functools.lru_cache(maxsize=512)
def _embed_sync(text: str, task_type: str) -> tuple[float, ...]:
    """Sync embed with LRU cache — query embeddings are often repeated."""
    response = _get_client().models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=settings.embedding_dim,
        ),
    )
    return tuple(response.embeddings[0].values)


def _embed_one_sync(text: str, task_type: str) -> list[float]:
    """Embed a single text with retry/backoff. embed_content(contents=list) returns
    only one embedding regardless of list length, so we embed one at a time."""
    for attempt in range(_MAX_RETRIES):
        try:
            response = _get_client().models.embed_content(
                model=settings.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=settings.embedding_dim,
                ),
            )
            return list(response.embeddings[0].values)
        except Exception as exc:
            msg = str(exc).lower()
            is_rate_limit = "429" in msg or "quota" in msg or "rate" in msg
            if is_rate_limit and attempt < _MAX_RETRIES - 1:
                # 429s need a real wait — exponential: 60s, 120s, 240s
                time.sleep(60 * (2 ** attempt))
                continue
            raise
    raise RuntimeError("unreachable")


def _embed_batch_sync(texts: list[str], task_type: str) -> list[list[float]]:
    """Embed a list of texts one at a time, throttled to stay under 15 RPM."""
    results = []
    for i, text in enumerate(texts):
        if i > 0:
            time.sleep(_INTER_DELAY)
        results.append(_embed_one_sync(text, task_type))
    return results


async def embed_text(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _embed_sync, text, task_type)
    return list(result)


async def embed_batch(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    """Embed arbitrarily many texts, chunking into ≤100-item batches."""
    loop = asyncio.get_running_loop()
    results: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        sub = texts[i : i + _BATCH_SIZE]
        batch_result = await loop.run_in_executor(None, _embed_batch_sync, sub, task_type)
        results.extend(batch_result)
    return results
