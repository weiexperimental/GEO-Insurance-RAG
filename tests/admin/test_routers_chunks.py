"""Tests for admin.backend.routers.chunks"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.chunks import router


def _make_app(chunk_service=None):
    app = FastAPI()
    app.include_router(router)
    if chunk_service is None:
        svc = MagicMock()
        svc.list_chunks.return_value = {"chunks": [], "total": 0, "page": 1, "size": 20}
        svc.get_quality_stats.return_value = {"good": 0, "warning": 0, "bad": 0, "total": 0}
        svc.get_token_distribution.return_value = {"buckets": []}
        svc.get_chunk.return_value = None
        svc.delete_chunk.return_value = True
        svc.batch_delete.return_value = {"deleted": 0, "total": 0}
        svc.update_chunk = AsyncMock(return_value={"id": "c1", "content": "new", "tokens": 5})
    else:
        svc = chunk_service
    app.state.chunk_service = svc
    return app, svc


class TestListChunks:
    def test_200_default_params(self):
        app, svc = _make_app()
        resp = TestClient(app).get("/api/chunks")
        assert resp.status_code == 200
        svc.list_chunks.assert_called_once_with(None, None, None, None, 1, 20)

    def test_passes_filters(self):
        app, svc = _make_app()
        TestClient(app).get("/api/chunks?doc_id=doc-1&type=footer&quality=bad&search=test&page=2&size=10")
        svc.list_chunks.assert_called_once_with("doc-1", "footer", "bad", "test", 2, 10)


class TestGetChunk:
    def test_404_when_not_found(self):
        app, _ = _make_app()
        resp = TestClient(app).get("/api/chunks/nonexistent")
        assert resp.status_code == 404

    def test_200_when_found(self):
        svc = MagicMock()
        svc.get_chunk.return_value = {"id": "c1", "content": "hi", "quality": "good", "quality_reasons": []}
        app, _ = _make_app(svc)
        resp = TestClient(app).get("/api/chunks/c1")
        assert resp.status_code == 200


class TestUpdateChunk:
    def test_200_on_success(self):
        app, svc = _make_app()
        resp = TestClient(app).put("/api/chunks/c1", json={"content": "updated"})
        assert resp.status_code == 200


class TestDeleteChunk:
    def test_200_on_success(self):
        app, _ = _make_app()
        resp = TestClient(app).delete("/api/chunks/c1")
        assert resp.status_code == 200

    def test_404_when_not_found(self):
        svc = MagicMock()
        svc.delete_chunk.return_value = False
        app, _ = _make_app(svc)
        resp = TestClient(app).delete("/api/chunks/nonexistent")
        assert resp.status_code == 404


class TestBatchDelete:
    def test_200_with_chunk_ids(self):
        app, svc = _make_app()
        resp = TestClient(app).post("/api/chunks/batch-delete", json={"chunk_ids": ["c1", "c2"]})
        assert resp.status_code == 200
        svc.batch_delete.assert_called_once_with(["c1", "c2"])


class TestStats:
    def test_200(self):
        app, _ = _make_app()
        assert TestClient(app).get("/api/chunks/stats").status_code == 200

    def test_passes_doc_id(self):
        app, svc = _make_app()
        TestClient(app).get("/api/chunks/stats?doc_id=doc-1")
        svc.get_quality_stats.assert_called_once_with("doc-1")


class TestTokenDistribution:
    def test_200(self):
        app, _ = _make_app()
        assert TestClient(app).get("/api/chunks/token-distribution").status_code == 200
