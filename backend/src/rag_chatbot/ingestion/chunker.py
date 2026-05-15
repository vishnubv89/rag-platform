"""
Text chunking strategies.

SemanticChunker (default): splits on paragraph and heading boundaries,
merges small paragraphs, guards oversized ones at sentence boundaries.
Produces chunks that map to coherent ideas rather than arbitrary token windows.

TokenChunker (legacy): original fixed-size sliding-window chunker.
Kept for backwards compatibility and as a fallback.
"""
import re
import tiktoken

from rag_chatbot.config import settings

_enc = tiktoken.get_encoding("cl100k_base")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token_len(text: str) -> int:
    return len(_enc.encode(text))


def _split_sentences(text: str) -> list[str]:
    """Split a paragraph into sentences on '. ', '? ', '! '."""
    parts = re.split(r'(?<=[.?!])\s+', text.strip())
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# SemanticChunker
# ---------------------------------------------------------------------------

def _semantic_chunks(text: str, size: int, overlap: int) -> list[str]:
    """
    1. Split on double-newlines (paragraphs) and Markdown headings.
    2. Merge consecutive short paragraphs until approaching `size` tokens.
    3. Split any paragraph that alone exceeds `size` at sentence boundaries.
    4. Prepend overlap tail of previous chunk for context continuity.
    """
    # Step 1 — split into raw paragraphs / headings
    raw = re.split(r'\n{2,}|(?=\n#{1,6}\s)', text)
    paragraphs = [p.strip() for p in raw if p.strip()]

    # Steps 2 & 3 — build atomic units (each fits within size)
    units: list[str] = []
    for para in paragraphs:
        if _token_len(para) <= size:
            units.append(para)
        else:
            sentences = _split_sentences(para)
            current = ""
            for sent in sentences:
                candidate = (current + " " + sent).strip()
                if _token_len(candidate) <= size:
                    current = candidate
                else:
                    if current:
                        units.append(current)
                    current = sent
            if current:
                units.append(current)

    # Step 4 — merge units greedily, prepend overlap tail
    chunks: list[str] = []
    current = ""
    prev_tail = ""

    for unit in units:
        candidate = (current + "\n\n" + unit).strip() if current else unit
        if _token_len(candidate) <= size:
            current = candidate
        else:
            if current:
                full = (prev_tail + "\n\n" + current).strip() if prev_tail else current
                chunks.append(full)
                tail_tokens = _enc.encode(current)[-overlap:] if overlap else []
                prev_tail = _enc.decode(tail_tokens).strip() if tail_tokens else ""
            current = unit

    if current:
        full = (prev_tail + "\n\n" + current).strip() if prev_tail else current
        chunks.append(full)

    return [c for c in chunks if c]


def semantic_chunk_text(text: str) -> list[str]:
    """Split text into semantically coherent chunks (default strategy)."""
    return _semantic_chunks(text, settings.chunk_size, settings.chunk_overlap)


# ---------------------------------------------------------------------------
# TokenChunker (legacy — fixed sliding window)
# ---------------------------------------------------------------------------

def chunk_text(text: str) -> list[str]:
    """Split text into overlapping token-bounded chunks (legacy strategy)."""
    tokens = _enc.encode(text)
    size = settings.chunk_size
    overlap = settings.chunk_overlap

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + size, len(tokens))
        chunk = _enc.decode(tokens[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(tokens):
            break
        start += size - overlap

    return chunks
