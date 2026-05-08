from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    backend_url: str = "http://localhost:8000"
    admin_secret_key: str = "change-me"
    app_env: str = "development"
    session_secret: str = "change-me-session-secret"


settings = Settings()
