# tests/test_config.py
import os
import importlib
import pytest
from unittest.mock import patch


def test_config_loads_all_model_settings():
    env = {
        "LLM_MODEL": "gpt-4o-mini",
        "LLM_API_KEY": "sk-test-llm",
        "LLM_API_BASE": "https://yibuapi.com/v1",
        "EMBEDDING_MODEL": "text-embedding-3-large",
        "EMBEDDING_API_KEY": "sk-test-embed",
        "EMBEDDING_API_BASE": "https://yibuapi.com/v1",
        "VISION_MODEL": "gpt-4o-mini",
        "VISION_API_KEY": "sk-test-vision",
        "VISION_API_BASE": "https://yibuapi.com/v1",
        "OPENSEARCH_HOST": "localhost",
        "OPENSEARCH_PORT": "9200",
    }
    with patch.dict(os.environ, env, clear=False):
        import src.config
        importlib.reload(src.config)
        cfg = src.config.load_config()
        assert cfg.llm.model == "gpt-4o-mini"
        assert cfg.llm.api_key == "sk-test-llm"
        assert cfg.llm.api_base == "https://yibuapi.com/v1"
        assert cfg.embedding.model == "text-embedding-3-large"
        assert cfg.embedding.api_key == "sk-test-embed"
        assert cfg.vision.model == "gpt-4o-mini"
        assert cfg.vision.api_key == "sk-test-vision"
        assert cfg.opensearch.host == "localhost"
        assert cfg.opensearch.port == 9200


def test_config_raises_on_missing_api_key():
    env = {
        "LLM_MODEL": "gpt-4o-mini",
        "EMBEDDING_API_KEY": "sk-test",
        "VISION_API_KEY": "sk-test",
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    import src.config
    importlib.reload(src.config)
    with patch.dict(os.environ, env, clear=True), \
         patch.object(src.config, "load_dotenv"):
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            src.config.load_config()


def test_config_default_paths():
    env = {
        "LLM_API_KEY": "sk-test",
        "EMBEDDING_API_KEY": "sk-test",
        "VISION_API_KEY": "sk-test",
    }
    with patch.dict(os.environ, env, clear=False):
        import src.config
        importlib.reload(src.config)
        cfg = src.config.load_config()
        assert "inbox" in cfg.paths.inbox_dir
        assert cfg.limits.max_file_size_mb == 100
