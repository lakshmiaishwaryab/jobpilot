from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "JobPilot API"
    database_url: str = "sqlite:///./jobpilot.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    follow_up_after_days: int = 7

    # Optional: enables LLM-written resume suggestions. Without a key the
    # API falls back to rule-based suggestions, so everything still works.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
