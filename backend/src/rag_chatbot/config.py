from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: str
    database_url: str

    # Gemini models
    llm_model: str = "gemini-2.0-flash"
    embedding_model: str = "text-embedding-004"
    embedding_dim: int = 768

    # Retrieval
    retrieval_top_k: int = 8
    grader_max_loops: int = 3

    # Chunking
    chunk_size: int = 300
    chunk_overlap: int = 50

    # Admin
    admin_secret_key: str = "change-me"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    app_env: str = "development"


settings = Settings()
