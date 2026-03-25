from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.queries import router


def _make_app():
    app = FastAPI()
    app.include_router(router)

    lr_svc = MagicMock()
    lr_svc.query = AsyncMock(return_value={"response": "答案在此", "sources": []})
    lr_svc.query_data = AsyncMock(return_value={"chunks": []})

    os_svc = MagicMock()
    os_svc.save_query_history = MagicMock()
    os_svc.get_query_history = MagicMock(return_value=[{"query": "test", "mode": "hybrid"}])

    app.state.lr_service = lr_svc
    app.state.os_service = os_svc
    return app, lr_svc, os_svc


def test_run_query_returns_200():
    app, _, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/queries", json={"query": "什麼是人壽保險？"})
    assert resp.status_code == 200


def test_run_query_includes_response_time_ms():
    app, _, _ = _make_app()
    client = TestClient(app)
    data = client.post("/api/queries", json={"query": "什麼是人壽保險？"}).json()
    assert "response_time_ms" in data
    assert isinstance(data["response_time_ms"], int)


def test_run_query_includes_lr_service_result():
    app, _, _ = _make_app()
    client = TestClient(app)
    data = client.post("/api/queries", json={"query": "test"}).json()
    assert "response" in data
    assert data["response"] == "答案在此"


def test_run_query_delegates_to_lr_service():
    app, lr_svc, _ = _make_app()
    client = TestClient(app)
    client.post("/api/queries", json={"query": "test", "mode": "local"})
    lr_svc.query.assert_called_once()
    call_args = lr_svc.query.call_args
    assert call_args[0][0] == "test"
    assert call_args[1]["mode"] == "local"


def test_run_query_saves_history():
    app, _, os_svc = _make_app()
    client = TestClient(app)
    client.post("/api/queries", json={"query": "test"})
    os_svc.save_query_history.assert_called_once()
    saved = os_svc.save_query_history.call_args[0][0]
    assert saved["query"] == "test"
    assert "response_time_ms" in saved
    assert "timestamp" in saved


def test_run_query_history_save_failure_still_returns_200():
    app = FastAPI()
    app.include_router(router)
    lr_svc = MagicMock()
    lr_svc.query = AsyncMock(return_value={"response": "ok"})
    os_svc = MagicMock()
    os_svc.save_query_history.side_effect = RuntimeError("opensearch down")
    app.state.lr_service = lr_svc
    app.state.os_service = os_svc

    client = TestClient(app)
    resp = client.post("/api/queries", json={"query": "test"})
    assert resp.status_code == 200


def test_run_query_optional_params_excluded_when_none():
    app, lr_svc, _ = _make_app()
    client = TestClient(app)
    client.post("/api/queries", json={"query": "test", "mode": "hybrid"})
    call_kwargs = lr_svc.query.call_args[1]
    # top_k, chunk_top_k, response_type are None by default — must not be in kwargs
    assert "top_k" not in call_kwargs
    assert "chunk_top_k" not in call_kwargs
    assert "response_type" not in call_kwargs


def test_run_query_optional_params_included_when_set():
    app, lr_svc, _ = _make_app()
    client = TestClient(app)
    client.post("/api/queries", json={"query": "test", "top_k": 5, "chunk_top_k": 10})
    call_kwargs = lr_svc.query.call_args[1]
    assert call_kwargs["top_k"] == 5
    assert call_kwargs["chunk_top_k"] == 10


def test_run_query_data_returns_200():
    app, _, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/queries/data", json={"query": "test"})
    assert resp.status_code == 200


def test_run_query_data_delegates_to_lr_service():
    app, lr_svc, _ = _make_app()
    client = TestClient(app)
    client.post("/api/queries/data", json={"query": "test", "mode": "global"})
    lr_svc.query_data.assert_called_once()
    call_args = lr_svc.query_data.call_args
    assert call_args[0][0] == "test"
    assert call_args[1]["mode"] == "global"


def test_get_history_returns_200():
    app, _, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/queries/history")
    assert resp.status_code == 200


def test_get_history_delegates_to_os_service():
    app, _, os_svc = _make_app()
    client = TestClient(app)
    client.get("/api/queries/history?limit=20")
    os_svc.get_query_history.assert_called_once_with(limit=20)


def test_get_history_returns_list():
    app, _, _ = _make_app()
    client = TestClient(app)
    data = client.get("/api/queries/history").json()
    assert isinstance(data, list)
