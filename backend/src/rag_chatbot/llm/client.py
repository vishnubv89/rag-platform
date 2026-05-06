"""
Unified LLM client. Supported providers (set via LLM_PROVIDER env var or
app_config table in the DB):

  gemini   — Google Gemini via google-genai SDK
  anthropic — Anthropic Claude via anthropic SDK
  nvidia   — NVIDIA NIM via OpenAI-compatible API
             (also works for OpenAI, Groq, Together AI, Ollama, etc.
              by overriding nvidia_base_url / nvidia_api_key in settings)
"""
import anthropic as _anthropic
import openai as _openai
from google import genai
from google.genai import types

from rag_chatbot.config import settings

# Cached per api_key so changing keys in the admin UI gets a fresh client.
_gemini_clients: dict[str, genai.Client] = {}
_anthropic_clients: dict[str, _anthropic.Anthropic] = {}
_openai_clients: dict[tuple[str, str], _openai.OpenAI] = {}


def _gemini(api_key: str) -> genai.Client:
    if api_key not in _gemini_clients:
        _gemini_clients[api_key] = genai.Client(api_key=api_key)
    return _gemini_clients[api_key]


def _anthropic_c(api_key: str) -> _anthropic.Anthropic:
    if api_key not in _anthropic_clients:
        _anthropic_clients[api_key] = _anthropic.Anthropic(api_key=api_key)
    return _anthropic_clients[api_key]


def _openai_c(base_url: str, api_key: str) -> _openai.OpenAI:
    key = (base_url, api_key)
    if key not in _openai_clients:
        _openai_clients[key] = _openai.OpenAI(base_url=base_url, api_key=api_key)
    return _openai_clients[key]


def generate(prompt: str, system: str = "", config: dict | None = None) -> str:
    """Generate a response using the configured LLM provider.

    config keys (all optional; fall back to env/settings when absent):
      llm_provider      — gemini | anthropic | nvidia
      llm_model         — Gemini model name
      gemini_api_key    — override GEMINI_API_KEY
      anthropic_model   — Anthropic model name
      anthropic_api_key — override ANTHROPIC_API_KEY
      nvidia_model      — model served by the OpenAI-compatible endpoint
      nvidia_api_key    — override NVIDIA_API_KEY
      nvidia_base_url   — base URL (default: integrate.api.nvidia.com/v1)
    """
    cfg = config or {}
    provider = cfg.get("llm_provider") or settings.llm_provider

    if provider == "anthropic":
        api_key = cfg.get("anthropic_api_key") or settings.anthropic_api_key
        if not api_key:
            raise ValueError("No Anthropic API key. Set it in Admin → Settings.")
        model = cfg.get("anthropic_model") or settings.anthropic_model
        msg = _anthropic_c(api_key).messages.create(
            model=model,
            max_tokens=1024,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    if provider == "nvidia":
        api_key = cfg.get("nvidia_api_key") or settings.nvidia_api_key
        if not api_key:
            raise ValueError("No NVIDIA API key. Set it in Admin → Settings.")
        model = cfg.get("nvidia_model") or settings.nvidia_model
        base_url = cfg.get("nvidia_base_url") or settings.nvidia_base_url
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = _openai_c(base_url, api_key).chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()

    # Default: Gemini
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
