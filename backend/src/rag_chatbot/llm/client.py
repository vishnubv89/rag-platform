import anthropic as _anthropic
from google import genai
from google.genai import types

from rag_chatbot.config import settings

# Keyed by api_key so switching keys in admin UI gets a fresh client
_gemini_clients: dict[str, genai.Client] = {}
_anthropic_clients: dict[str, _anthropic.Anthropic] = {}


def _gemini(api_key: str) -> genai.Client:
    if api_key not in _gemini_clients:
        _gemini_clients[api_key] = genai.Client(api_key=api_key)
    return _gemini_clients[api_key]


def _anthropic_client(api_key: str) -> _anthropic.Anthropic:
    if api_key not in _anthropic_clients:
        _anthropic_clients[api_key] = _anthropic.Anthropic(api_key=api_key)
    return _anthropic_clients[api_key]


def generate(prompt: str, system: str = "", config: dict | None = None) -> str:
    """Generate a response using the configured LLM provider.

    config dict keys (all optional, fall back to env/settings):
      llm_provider      — "gemini" | "anthropic"
      llm_model         — Gemini model name
      gemini_api_key    — override env GEMINI_API_KEY
      anthropic_model   — Anthropic model name
      anthropic_api_key — override env ANTHROPIC_API_KEY
    """
    cfg = config or {}
    provider = cfg.get("llm_provider") or settings.llm_provider

    if provider == "anthropic":
        api_key = cfg.get("anthropic_api_key") or settings.anthropic_api_key
        if not api_key:
            raise ValueError(
                "No Anthropic API key configured. Set it in Admin → Settings → Anthropic API Key."
            )
        model = cfg.get("anthropic_model") or settings.anthropic_model
        msg = _anthropic_client(api_key).messages.create(
            model=model,
            max_tokens=1024,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    # Gemini (default)
    api_key = cfg.get("gemini_api_key") or settings.gemini_api_key
    model = cfg.get("llm_model") or settings.llm_model
    response = _gemini(api_key).models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=0.0,
        ),
    )
    return response.text.strip()
