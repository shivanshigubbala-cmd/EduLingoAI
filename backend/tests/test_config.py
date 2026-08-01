"""Tests for backend/src/config.py — P0-SHR1 config management."""

import pytest


def _fresh_settings(**env_overrides):
    """Helper: get a fresh Settings instance, ignoring any real .env file on
    disk, using only explicitly provided overrides (falls back to field
    defaults otherwise). Passing _env_file=None prevents pydantic-settings
    from reading the actual .env file, which previously leaked real local
    secrets into tests expecting defaults.
    """
    from src.config import Settings, get_settings

    get_settings.cache_clear()
    try:
        return Settings(_env_file=None, **env_overrides)
    finally:
        get_settings.cache_clear()


class TestSettingsLoadCorrectly:
    """(a) Settings load correctly when required env vars are set."""

    def test_loads_with_all_env_vars(self):
        env = {
            "LLM_API_KEY": "sk-test-key",
            "EMBEDDING_API_KEY": "sk-embed-key",
            "DATABASE_URL": "postgresql://user:pass@host:5432/db",
            "JWT_SECRET": "my-secret",
            "VECTOR_STORE_URL": "http://qdrant:6333",
        }
        settings = _fresh_settings(**env)

        assert settings.LLM_API_KEY == "sk-test-key"
        assert settings.EMBEDDING_API_KEY == "sk-embed-key"
        assert settings.DATABASE_URL == "postgresql://user:pass@host:5432/db"
        assert settings.JWT_SECRET == "my-secret"
        assert settings.VECTOR_STORE_URL == "http://qdrant:6333"


class TestDefaultModelValues:
    """(b) Default model values are correct."""

    def test_llm_model_defaults(self):
        settings = _fresh_settings()
        assert settings.LLM_MODEL == "llama3.2:1b"

    def test_llm_fast_model_defaults(self):
        settings = _fresh_settings()
        assert settings.LLM_FAST_MODEL == "claude-haiku-3"

    def test_embedding_model_defaults(self):
        settings = _fresh_settings()
        assert settings.EMBEDDING_MODEL == "text-embedding-3-small"

    def test_vector_store_url_default(self):
        settings = _fresh_settings()
        assert settings.VECTOR_STORE_URL == "http://localhost:6333"

    def test_api_keys_default_to_empty(self):
        settings = _fresh_settings()
        assert settings.LLM_API_KEY == ""
        assert settings.EMBEDDING_API_KEY == ""


class TestEnvVarOverrides:
    """(c) Environment variable overrides work."""

    def test_override_llm_model(self):
        settings = _fresh_settings(LLM_MODEL="claude-3-opus")
        assert settings.LLM_MODEL == "claude-3-opus"

    def test_override_embedding_model(self):
        settings = _fresh_settings(EMBEDDING_MODEL="text-embedding-3-large")
        assert settings.EMBEDDING_MODEL == "text-embedding-3-large"

    def test_override_vector_store_url(self):
        settings = _fresh_settings(VECTOR_STORE_URL="http://remote-qdrant:6333")
        assert settings.VECTOR_STORE_URL == "http://remote-qdrant:6333"

    def test_override_database_url(self):
        settings = _fresh_settings(DATABASE_URL="postgresql://other:5432/otherdb")
        assert settings.DATABASE_URL == "postgresql://other:5432/otherdb"