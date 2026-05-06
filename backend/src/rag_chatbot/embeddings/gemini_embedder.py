import asyncio
import functools

from google import genai
from google.genai import types

from rag_chatbot.config import settings

_client: genai.Client | None = None


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


async def embed_text(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _embed_sync, text, task_type)
    return list(result)


async def embed_batch(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    """Embed a batch of texts. Gemini supports up to 100 per request."""
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _get_client().models.embed_content(
            model=settings.embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.embedding_dim,
            ),
        ),
    )
    return [list(e.values) for e in response.embeddings]
