import tiktoken

from rag_chatbot.config import settings

_enc = tiktoken.get_encoding("cl100k_base")


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping token-bounded chunks."""
    tokens = _enc.encode(text)
    size = settings.chunk_size
    overlap = settings.chunk_overlap

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk = _enc.decode(chunk_tokens).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(tokens):
            break
        start += size - overlap

    return chunks
