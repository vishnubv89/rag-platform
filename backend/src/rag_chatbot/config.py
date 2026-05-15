from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: str
    database_url: str

    # LLM provider: "gemini" or "anthropic"
    llm_provider: str = "gemini"

    # Gemini
    llm_model: str = "gemini-2.0-flash"
    embedding_model: str = "models/gemini-embedding-2"
    embedding_dim: int = 768

    # Anthropic (used when llm_provider="anthropic")
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # NVIDIA / any OpenAI-compatible API (used when llm_provider="nvidia")
    # Setting nvidia_base_url to another endpoint makes this work for OpenAI,
    # Groq, Together AI, Ollama, etc. — any OpenAI-compatible provider.
    nvidia_api_key: str = ""
    nvidia_model: str = "meta/llama-3.2-3b-instruct"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # Retrieval
    retrieval_top_k: int = 8
    grader_max_loops: int = 3

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 100

    # Admin
    admin_secret_key: str = "change-me"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    app_env: str = "development"

    # Auth / JWT (local password login)
    jwt_secret: str = "change-me-jwt-secret"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7

    # Zitadel OIDC (SSO login)
    # Set to the Zitadel issuer URL, e.g. http://localhost:8088
    # Leave empty to disable OIDC token acceptance.
    zitadel_issuer: str = ""
    # Internal URL used by the backend to fetch Zitadel's JWKS.
    # When running in Docker Compose the backend cannot reach "localhost:8088"
    # (the host-mapped port); it must use the internal service name instead.
    # Defaults to zitadel_issuer when not set (works for local dev outside Docker).
    zitadel_internal_url: str = ""
    # Shared secret between Zitadel Actions and this backend.
    # Zitadel sends this in X-Zitadel-Secret header on every enrich call.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    zitadel_action_secret: str = ""

    # Frontend (User Agent / PKCE) application Client ID registered in Zitadel.
    # Zitadel sets `aud` to this value in access tokens issued to the browser.
    zitadel_frontend_client_id: str = ""
    # Backend (API) application Client ID registered in Zitadel.
    # Used for server-to-server token validation (e.g. OBO exchange).
    # Leave empty to skip strict audience validation.
    zitadel_backend_client_id: str = ""

    # Langfuse observability (optional — disabled when secret key is empty)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://langfuse:3000"


settings = Settings()
