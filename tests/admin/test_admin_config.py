import pytest
from admin.backend.config import Settings, load_settings


def test_default_settings():
    s = Settings()
    assert s.opensearch_host == "localhost"
    assert s.opensearch_port == 9200
    assert s.lightrag_api_url == "http://localhost:9621"
    assert s.log_dir == "./logs"
    assert s.port == 8080


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_HOST", "opensearch")
    monkeypatch.setenv("OPENSEARCH_PORT", "9201")
    monkeypatch.setenv("LIGHTRAG_API_URL", "http://lightrag:9621")
    s = load_settings()
    assert s.opensearch_host == "opensearch"
    assert s.opensearch_port == 9201
    assert s.lightrag_api_url == "http://lightrag:9621"


def test_settings_has_model_configs(monkeypatch):
    """Settings should expose llm and embedding model configs."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-llm")
    monkeypatch.setenv("LLM_API_BASE", "https://api.test.com/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test-embed")
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://api.test.com/v1")
    settings = load_settings()
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_api_key == "sk-test-llm"
    assert settings.llm_api_base == "https://api.test.com/v1"
    assert settings.embedding_model == "text-embedding-3-large"
    assert settings.embedding_api_key == "sk-test-embed"
    assert settings.embedding_api_base == "https://api.test.com/v1"
