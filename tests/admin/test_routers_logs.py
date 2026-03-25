import json
import os
import tempfile
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.logs import router
from admin.backend.config import Settings


def _make_app(log_dir: str):
    app = FastAPI()
    app.include_router(router)
    app.state.settings = Settings(log_dir=log_dir)
    app.state.os_service = MagicMock()
    return app


def _write_log(log_dir: str, date: str, entries: list):
    path = os.path.join(log_dir, f"rag-{date}.log")
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return path


# ---------------------------------------------------------------------------
# GET /api/logs/dates
# ---------------------------------------------------------------------------

def test_list_log_dates_returns_dates():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_log(tmpdir, "2026-03-22", [{"level": "INFO", "msg": "started"}])
        _write_log(tmpdir, "2026-03-21", [{"level": "INFO", "msg": "ok"}])
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/dates").json()
        assert "2026-03-22" in data
        assert "2026-03-21" in data


def test_list_log_dates_returns_newest_first():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_log(tmpdir, "2026-03-20", [])
        _write_log(tmpdir, "2026-03-22", [])
        _write_log(tmpdir, "2026-03-21", [])
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/dates").json()
        assert data[0] == "2026-03-22"


def test_list_log_dates_empty_when_dir_missing():
    app = _make_app("/nonexistent/path")
    client = TestClient(app)
    data = client.get("/api/logs/dates").json()
    assert data == []


def test_list_log_dates_ignores_non_log_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        # write a non-matching file
        with open(os.path.join(tmpdir, "other.txt"), "w") as f:
            f.write("ignore me\n")
        _write_log(tmpdir, "2026-03-22", [{"msg": "hi"}])
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/dates").json()
        assert data == ["2026-03-22"]


# ---------------------------------------------------------------------------
# GET /api/logs/{date}
# ---------------------------------------------------------------------------

def test_get_logs_returns_entries():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_log(tmpdir, "2026-03-22", [
            {"level": "INFO", "msg": "hello"},
            {"level": "ERROR", "msg": "oops"},
        ])
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2026-03-22").json()
        assert data["total"] == 2
        assert len(data["entries"]) == 2
        assert data["entries"][0]["msg"] == "hello"


def test_get_logs_missing_date_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2099-01-01").json()
        assert data == {"entries": [], "total": 0}


def test_get_logs_limit_applies():
    with tempfile.TemporaryDirectory() as tmpdir:
        entries = [{"i": i} for i in range(100)]
        _write_log(tmpdir, "2026-03-22", entries)
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2026-03-22?limit=10").json()
        assert len(data["entries"]) == 10
        assert data["total"] == 100
        # should be the last 10
        assert data["entries"][0]["i"] == 90


def test_get_logs_handles_raw_non_json_lines():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "rag-2026-03-22.log")
        with open(path, "w") as f:
            f.write("not json at all\n")
            f.write(json.dumps({"level": "INFO"}) + "\n")
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2026-03-22").json()
        assert data["total"] == 2
        raw_entries = [e for e in data["entries"] if "raw" in e]
        assert len(raw_entries) == 1
        assert raw_entries[0]["raw"] == "not json at all"


# ---------------------------------------------------------------------------
# GET /api/logs/{date}/search
# ---------------------------------------------------------------------------

def test_search_logs_filters_entries():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_log(tmpdir, "2026-03-22", [
            {"level": "INFO", "msg": "ingestion started"},
            {"level": "ERROR", "msg": "connection failed"},
            {"level": "INFO", "msg": "ingestion complete"},
        ])
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2026-03-22/search?q=ingestion").json()
        assert data["total"] == 2
        assert all("ingestion" in json.dumps(e) for e in data["entries"])


def test_search_logs_case_insensitive():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_log(tmpdir, "2026-03-22", [
            {"level": "INFO", "msg": "Ingestion started"},
            {"level": "ERROR", "msg": "other error"},
        ])
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2026-03-22/search?q=INGESTION").json()
        assert data["total"] == 1


def test_search_logs_missing_date_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2099-01-01/search?q=anything").json()
        assert data == {"entries": [], "total": 0}


def test_search_logs_requires_q():
    with tempfile.TemporaryDirectory() as tmpdir:
        app = _make_app(tmpdir)
        client = TestClient(app)
        resp = client.get("/api/logs/2026-03-22/search")
        assert resp.status_code == 422


def test_search_logs_no_matches_returns_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_log(tmpdir, "2026-03-22", [{"msg": "hello"}, {"msg": "world"}])
        app = _make_app(tmpdir)
        client = TestClient(app)
        data = client.get("/api/logs/2026-03-22/search?q=XYZNOTFOUND").json()
        assert data["total"] == 0
        assert data["entries"] == []
