"""
Application configuration.

All settings are read from environment variables or a .env file.

Secrets such as API keys and JWT secrets must be stored in .env
and must never be hardcoded in the source code.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings."""

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    app_name: str = "Personal Knowledge-Base MCP Server"
    debug: bool = False

    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    frontend_origin: str = "http://localhost:3000"

    # ------------------------------------------------------------------ #
    # Qdrant
    # ------------------------------------------------------------------ #
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "study_notes"

    # ------------------------------------------------------------------ #
    # Embeddings
    # ------------------------------------------------------------------ #
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # OpenAI API key
    openai_api_key: str = ""

    # ------------------------------------------------------------------ #
    # Authentication
    # ------------------------------------------------------------------ #
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(
        default=60,
        gt=0,
    )

    # JSON object containing server-side users
    auth_users_json: str = "{}"

    # ------------------------------------------------------------------ #
    # Environment configuration
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()