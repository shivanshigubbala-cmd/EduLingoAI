"""Centralized application configuration loaded from environment variables.

Never hardcode API keys or secrets here — all sensitive values come from
the environment (or a .env file loaded at process start).

Usage:
    from src.config import get_settings
    settings = get_settings()
    print(settings.LLM_MODEL)
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — every field maps to an env var (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://student_ai:change_me@localhost:5432/student_ai_tool"

    # ── Auth ──────────────────────────────────────────────────────────────
    JWT_SECRET: str = "change_me"
    OAUTH_CLIENT_ID: str = ""
    OAUTH_CLIENT_SECRET: str = ""

    # ── LLM — Anthropic Claude (P0-SHR1) ─────────────────────────────────
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_FAST_MODEL: str = "claude-haiku-3"

    # ── Embeddings — OpenAI text-embedding-3-small (P0-SHR1) ──────────────
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ── Vector Store — Qdrant (P0-SHR1) ──────────────────────────────────
    VECTOR_STORE_URL: str = "http://localhost:6333"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Using @lru_cache ensures the Settings object is created lazily (only on
    first call) and then reused.  This avoids crashing test collection or CI
    runs where environment variables are not set — the object is simply never
    instantiated unless code explicitly calls get_settings().
    """
    return Settings()
