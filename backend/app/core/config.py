"""
Application configuration.

All settings are read from environment variables (or a .env file via python-dotenv).
Never hardcode secrets here — use .env.example to document required variables.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object populated from environment variables."""

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    app_name: str = "Personal Knowledge-Base MCP Server"
    debug: bool = False

    # ------------------------------------------------------------------ #
    # CORS — comma-separated allowed origins for the FastAPI backend
    # ------------------------------------------------------------------ #
    frontend_origin: str = "http://localhost:3000"

    # ------------------------------------------------------------------ #
    # Qdrant (vector database) — not wired up in Phase 1
    # ------------------------------------------------------------------ #
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # ------------------------------------------------------------------ #
    # Embeddings — provider and model are kept configurable so the
    # retrieval logic never has to change when swapping providers.
    # ------------------------------------------------------------------ #
    embedding_provider: str = "openai"   # e.g. "openai" | "huggingface" | "cohere"
    embedding_model: str = "text-embedding-3-small"

    # ------------------------------------------------------------------ #
    # Authentication
    # ------------------------------------------------------------------ #
    jwt_secret_key: str = "change-me-before-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
