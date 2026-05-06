from pathlib import Path
import PyPDF2


def load_file(path: str | Path) -> str:
    """Load text content from a PDF, txt, or md file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(p)
    elif suffix in {".txt", ".md"}:
        return p.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _load_pdf(path: Path) -> str:
    text_parts: list[str] = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)
