import anthropic as _anthropic
from google import genai
from google.genai import types

from rag_chatbot.config import settings

_gemini_client: genai.Client | None = None
_anthropic_client: _anthropic.Anthropic | None = None


def _gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def _anthropic_c() -> _anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Set it in your environment or .env file."
            )
        _anthropic_client = _anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def generate(prompt: str, system: str = "") -> str:
    """Generate a response using the configured LLM provider."""
    if settings.llm_provider == "anthropic":
        msg = _anthropic_c().messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    # Default: Gemini
    response = _gemini().models.generate_content(
        model=settings.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=0.0,
        ),
    )
    return response.text.strip()
