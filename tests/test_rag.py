# tests/test_rag.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_rag_engine_initializes():
    from src.config import ModelConfig, OpenSearchConfig

    llm_cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
    embed_cfg = ModelConfig(model="text-embedding-3-large", api_key="sk-test", api_base="https://test.com/v1")
    vision_cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
    os_cfg = OpenSearchConfig(host="localhost", port=9200)

    with patch("src.rag.LightRAG") as mock_lr, \
         patch("src.rag.RAGAnything") as mock_ra, \
         patch("src.rag.EmbeddingFunc") as mock_ef:
        mock_lr_instance = AsyncMock()
        mock_lr.return_value = mock_lr_instance

        from src.rag import RAGEngine
        engine = RAGEngine(
            llm_config=llm_cfg,
            embedding_config=embed_cfg,
            vision_config=vision_cfg,
            opensearch_config=os_cfg,
            working_dir="/tmp/test-rag",
        )
        await engine.initialize()

        mock_lr.assert_called_once()
        mock_lr_instance.initialize_storages.assert_awaited_once()
        mock_ra.assert_called_once()


@pytest.mark.asyncio
async def test_rag_engine_query():
    from src.rag import RAGEngine

    engine = RAGEngine.__new__(RAGEngine)
    engine._rag = AsyncMock()
    engine._rag.aquery.return_value = "test result"
    engine._lightrag = MagicMock()

    result = await engine.query("test question", mode="hybrid")
    engine._rag.aquery.assert_awaited_once_with("test question", mode="hybrid", top_k=5)
    assert result == "test result"
