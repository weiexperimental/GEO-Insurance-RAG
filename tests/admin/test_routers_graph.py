from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.graph import router


def _make_app():
    app = FastAPI()
    app.include_router(router)

    graph_svc = MagicMock()
    graph_svc.get_graph = MagicMock(
        return_value={"nodes": [{"id": "A"}], "edges": [{"source": "A", "target": "B"}]}
    )
    graph_svc.search_entities = MagicMock(return_value=["保險", "人壽"])
    graph_svc.get_popular_entities = MagicMock(return_value=["保險", "醫療"])

    app.state.graph_service = graph_svc
    return app, graph_svc


def test_get_graph_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/graph")
    assert resp.status_code == 200


def test_get_graph_has_nodes_and_edges():
    app, _ = _make_app()
    client = TestClient(app)
    data = client.get("/api/graph").json()
    assert "nodes" in data
    assert "edges" in data


def test_get_graph_passes_params():
    app, graph_svc = _make_app()
    client = TestClient(app)
    client.get("/api/graph?types=保險&max_nodes=100")
    graph_svc.get_graph.assert_called_once_with(type_filter=["保險"], doc_filter=None, max_nodes=100)


def test_get_graph_default_params():
    app, graph_svc = _make_app()
    client = TestClient(app)
    client.get("/api/graph")
    graph_svc.get_graph.assert_called_once_with(type_filter=None, doc_filter=None, max_nodes=200)


def test_search_labels_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/graph/search?q=test")
    assert resp.status_code == 200


def test_search_labels_returns_list():
    app, _ = _make_app()
    client = TestClient(app)
    data = client.get("/api/graph/search?q=保險").json()
    assert isinstance(data, list)


def test_search_labels_passes_query():
    app, graph_svc = _make_app()
    client = TestClient(app)
    client.get("/api/graph/search?q=保險&limit=20")
    graph_svc.search_entities.assert_called_once_with("保險", 20)


def test_search_labels_requires_q():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/graph/search")
    assert resp.status_code == 422


def test_popular_labels_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/graph/popular")
    assert resp.status_code == 200


def test_popular_labels_returns_list():
    app, _ = _make_app()
    client = TestClient(app)
    data = client.get("/api/graph/popular").json()
    assert isinstance(data, list)


def test_popular_labels_passes_limit():
    app, graph_svc = _make_app()
    client = TestClient(app)
    client.get("/api/graph/popular?limit=10")
    graph_svc.get_popular_entities.assert_called_once_with(10)
