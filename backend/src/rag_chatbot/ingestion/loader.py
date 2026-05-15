from pathlib import Path
import re
import PyPDF2


def _sanitize(text: str) -> str:
    """Remove null bytes and other characters PostgreSQL UTF8 rejects."""
    return re.sub(r"\x00", "", text)


def load_file(path: str | Path) -> str:
    """Load text content from a PDF, txt, or md file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        text = _load_pdf(p)
    elif suffix in {".txt", ".md"}:
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    return _sanitize(text)


def _load_pdf(path: Path) -> str:
    text_parts: list[str] = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text = page.extract_text() or ""
            text_parts.append(text)
    return "\n\n".join(text_parts)
