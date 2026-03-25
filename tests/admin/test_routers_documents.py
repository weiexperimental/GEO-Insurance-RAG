import io
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.documents import router


def _make_app():
    app = FastAPI()
    app.include_router(router)

    os_svc = MagicMock()
    os_svc.get_ingestion_statuses.return_value = {"docs": [], "total": 0}
    os_svc.get_ingestion_analytics.return_value = {"by_status": {}}

    app.state.os_service = os_svc
    return app, os_svc


def test_list_documents_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/documents")
    assert resp.status_code == 200


def test_list_documents_delegates_to_os_service():
    app, os_svc = _make_app()
    client = TestClient(app)
    client.get("/api/documents?limit=10&offset=5&status=done")
    os_svc.get_ingestion_statuses.assert_called_once_with(limit=10, offset=5, status_filter="done")


def test_list_documents_default_params():
    app, os_svc = _make_app()
    client = TestClient(app)
    client.get("/api/documents")
    os_svc.get_ingestion_statuses.assert_called_once_with(limit=50, offset=0, status_filter=None)


def test_get_analytics_returns_200():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.get("/api/documents/analytics")
    assert resp.status_code == 200


def test_get_analytics_delegates_to_os_service():
    app, os_svc = _make_app()
    client = TestClient(app)
    client.get("/api/documents/analytics")
    os_svc.get_ingestion_analytics.assert_called_once()


# upload, scan, reprocess return 501 (not implemented in admin dashboard)

def test_upload_returns_501():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
    )
    assert resp.status_code == 501


def test_scan_returns_501():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/documents/scan")
    assert resp.status_code == 501


def test_reprocess_returns_501():
    app, _ = _make_app()
    client = TestClient(app)
    resp = client.post("/api/documents/reprocess")
    assert resp.status_code == 501


# delete uses OpenSearch directly

def test_delete_document_returns_200():
    app, os_svc = _make_app()
    client = TestClient(app)
    resp = client.delete("/api/documents/doc-123")
    assert resp.status_code == 200
    os_svc._client.delete.assert_called_once_with(index="doc_status", id="doc-123")


def test_delete_document_404_when_not_found():
    app, os_svc = _make_app()
    os_svc._client.delete.side_effect = Exception("Not Found")
    client = TestClient(app)
    resp = client.delete("/api/documents/nonexistent")
    assert resp.status_code == 404
