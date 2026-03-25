from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.system import router


def _make_app():
    app = FastAPI()
    app.include_router(router)

    os_svc = MagicMock()
    os_svc.get_system_overview.return_value = {"total_docs": 10}
    os_svc.get_cluster_health.return_value = {"status": "green"}
    os_svc.get_node_stats.return_value = {"nodes": {}}
    os_svc.get_knn_stats.return_value = {"knn": "ok"}

    app.state.os_service = os_svc
    return app, os_svc


def test_get_health_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/system/health")
    assert resp.status_code == 200


def test_get_health_has_expected_keys():
    app, _ = _make_app()
    client = TestClient(app)
    data = client.get("/api/system/health").json()
    assert "overview" in data
    assert "cluster" in data
    assert "nodes" in data
    assert "knn" in data


def test_get_health_delegates_to_os_service():
    app, os_svc = _make_app()
    client = TestClient(app)
    client.get("/api/system/health")
    os_svc.get_system_overview.assert_called_once()
    os_svc.get_cluster_health.assert_called_once()
    os_svc.get_node_stats.assert_called_once()
    os_svc.get_knn_stats.assert_called_once()


def test_get_health_knn_exception_returns_empty_dict():
    app = FastAPI()
    app.include_router(router)
    os_svc = MagicMock()
    os_svc.get_system_overview.return_value = {}
    os_svc.get_cluster_health.return_value = {}
    os_svc.get_node_stats.return_value = {}
    os_svc.get_knn_stats.side_effect = RuntimeError("knn unavailable")
    app.state.os_service = os_svc

    client = TestClient(app)
    data = client.get("/api/system/health").json()
    assert data["knn"] == {}
