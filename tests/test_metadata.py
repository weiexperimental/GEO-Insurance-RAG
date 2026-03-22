# tests/test_metadata.py
import json
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_extract_metadata_returns_structured_data():
    mock_response = json.dumps({
        "company": "AXA 安盛",
        "product_name": "智尊守慧醫療保障",
        "product_type": "醫療",
        "document_type": "產品小冊子",
        "document_date": "2026-01",
    })

    with patch("src.metadata.openai_complete_if_cache", new_callable=AsyncMock, return_value=mock_response):
        from src.metadata import extract_metadata
        from src.config import ModelConfig

        cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
        result = await extract_metadata("AXA安盛智尊守慧醫療保障產品小冊子內容...", cfg)

        assert result["company"] == "AXA 安盛"
        assert result["product_name"] == "智尊守慧醫療保障"
        assert result["product_type"] == "醫療"
        assert result["document_type"] == "產品小冊子"
        assert result["document_date"] == "2026-01"


@pytest.mark.asyncio
async def test_extract_metadata_returns_empty_on_failure():
    with patch("src.metadata.openai_complete_if_cache", new_callable=AsyncMock, side_effect=Exception("API down")):
        from src.metadata import extract_metadata
        from src.config import ModelConfig

        cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
        result = await extract_metadata("some content", cfg)

        assert result == {}
