import pytest
from unittest.mock import AsyncMock, MagicMock, patch

MOCK_AQUERY_LLM_RESULT = {
    "status": "success",
    "data": {
        "entities": [{"entity_name": "AXA", "entity_type": "organization"}],
        "relationships": [{"src_id": "AXA", "tgt_id": "保險", "weight": 1.0}],
        "chunks": [{"content": "AXA 危疾保障...", "chunk_id": "c1"}],
        "references": [{"reference_id": "ref-1", "file_path": "test.pdf"}],
    },
    "metadata": {
        "query_mode": "hybrid",
        "keywords": {"high_level": ["保險"], "low_level": ["AXA"]},
        "processing_info": {
            "total_entities_found": 10,
            "entities_after_truncation": 1,
            "total_relations_found": 5,
            "relations_after_truncation": 1,
            "merged_chunks_count": 20,
            "final_chunks_count": 1,
        },
    },
    "llm_response": {"content": "根據資料...", "is_streaming": False},
}


def _make_service():
    lr = AsyncMock()
    lr.aquery_llm = AsyncMock(return_value=MOCK_AQUERY_LLM_RESULT)
    lr.aquery_data = AsyncMock(return_value={
        **MOCK_AQUERY_LLM_RESULT,
        "llm_response": None,
    })
    lr.aquery = AsyncMock(return_value="System prompt\n\nContext: ...")
    from admin.backend.services.query_playground import QueryPlaygroundService
    return QueryPlaygroundService(lr), lr


@pytest.mark.asyncio
async def test_query_full_returns_normalized_response():
    svc, lr = _make_service()
    result = await svc.query_full("test query", mode="hybrid", top_k=5,
                                  chunk_top_k=10, enable_rerank=True)
    assert result["status"] == "success"
    assert result["llm_response"] == "根據資料..."
    assert result["data"]["keywords"]["high_level"] == ["保險"]
    assert "total_ms" in result["timing"]
    assert isinstance(result["full_prompt"], str)


@pytest.mark.asyncio
async def test_query_full_sets_include_references():
    svc, lr = _make_service()
    await svc.query_full("test", mode="hybrid", top_k=5,
                         chunk_top_k=10, enable_rerank=True)
    call_args = lr.aquery_llm.call_args
    param = call_args[0][1]
    assert getattr(param, "include_references", None) is True


@pytest.mark.asyncio
async def test_retrieve_only_has_no_llm_response():
    svc, _ = _make_service()
    result = await svc.retrieve_only("test", mode="hybrid", top_k=5,
                                     chunk_top_k=10, enable_rerank=True)
    assert result["llm_response"] is None
    assert result["full_prompt"] is None
    assert "retrieval_ms" in result["timing"]


@pytest.mark.asyncio
async def test_compare_returns_two_results():
    svc, _ = _make_service()
    params = {"mode": "hybrid", "top_k": 5, "chunk_top_k": 10, "enable_rerank": True}
    result = await svc.compare("test", params, params)
    assert "result_a" in result
    assert "result_b" in result
    assert result["result_a"]["status"] == "success"
    assert result["result_b"]["status"] == "success"
