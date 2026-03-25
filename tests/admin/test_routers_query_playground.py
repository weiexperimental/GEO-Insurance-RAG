import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.query_playground import router

MOCK_RESULT = {
    "status": "success",
    "data": {"keywords": {}, "entities": [], "relationships": [], "chunks": [], "references": []},
    "metadata": {"query_mode": "hybrid", "processing_info": {}},
    "full_prompt": "test prompt",
    "llm_response": "test response",
    "timing": {"total_ms": 100},
}


def _make_app():
    app = FastAPI()
    app.include_router(router)
    svc = AsyncMock()
    svc.query_full = AsyncMock(return_value=MOCK_RESULT)
    svc.retrieve_only = AsyncMock(return_value={**MOCK_RESULT, "llm_response": None})
    svc.compare = AsyncMock(return_value={"result_a": MOCK_RESULT, "result_b": MOCK_RESULT})
    app.state.playground_service = svc
    return app, svc


def test_query_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/playground/query", json={
        "query": "test", "mode": "hybrid", "top_k": 5,
        "chunk_top_k": 10, "enable_rerank": True,
    })
    assert resp.status_code == 200


def test_query_passes_params():
    app, svc = _make_app()
    client = TestClient(app)
    client.post("/api/playground/query", json={
        "query": "AXA 危疾", "mode": "naive", "top_k": 10,
        "chunk_top_k": 20, "enable_rerank": False,
    })
    svc.query_full.assert_called_once_with(
        "AXA 危疾", mode="naive", top_k=10, chunk_top_k=20, enable_rerank=False,
    )


def test_retrieve_only_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/playground/retrieve-only", json={
        "query": "test", "mode": "hybrid", "top_k": 5,
        "chunk_top_k": 10, "enable_rerank": True,
    })
    assert resp.status_code == 200


def test_compare_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    params = {"mode": "hybrid", "top_k": 5, "chunk_top_k": 10, "enable_rerank": True}
    resp = client.post("/api/playground/compare", json={
        "query": "test", "params_a": params, "params_b": params,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "result_a" in data
    assert "result_b" in data


def test_query_requires_query_field():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/playground/query", json={"mode": "hybrid"})
    assert resp.status_code == 422


def test_query_validates_mode():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/playground/query", json={
        "query": "test", "mode": "invalid_mode", "top_k": 5,
        "chunk_top_k": 10, "enable_rerank": True,
    })
    assert resp.status_code == 422
