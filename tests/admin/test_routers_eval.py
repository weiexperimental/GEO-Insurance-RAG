"""Tests for admin.backend.routers.eval"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin.backend.routers.eval import router


def _make_app(eval_service=None):
    app = FastAPI()
    app.include_router(router)
    if eval_service is None:
        svc = MagicMock()
        svc.list_qa_pairs.return_value = {"pairs": [], "total": 0, "page": 1, "size": 20}
        svc.create_qa_pair.return_value = {"id": "qa-1", "question": "q?", "status": "approved"}
        svc.update_qa_pair.return_value = {"id": "qa-1", "question": "updated"}
        svc.delete_qa_pair.return_value = True
        svc.batch_update_status.return_value = {"updated": 2, "total": 2}
        svc.generate_qa_pairs = AsyncMock(return_value={"generated": 5})
        svc.run_evaluation = AsyncMock(return_value={"run_id": "run-1", "scores": {}})
        svc.list_eval_runs.return_value = []
        svc.get_eval_run.return_value = None
    else:
        svc = eval_service
    app.state.eval_service = svc
    return app, svc


class TestQAPairsCRUD:
    def test_list_200(self):
        app, _ = _make_app()
        assert TestClient(app).get("/api/eval/qa-pairs").status_code == 200

    def test_create_200(self):
        app, _ = _make_app()
        resp = TestClient(app).post("/api/eval/qa-pairs", json={"question": "q?", "expected_answer": "a"})
        assert resp.status_code == 200

    def test_update_200(self):
        app, _ = _make_app()
        resp = TestClient(app).put("/api/eval/qa-pairs/qa-1", json={"question": "new?"})
        assert resp.status_code == 200

    def test_delete_200(self):
        app, _ = _make_app()
        assert TestClient(app).delete("/api/eval/qa-pairs/qa-1").status_code == 200

    def test_delete_404(self):
        svc = MagicMock()
        svc.delete_qa_pair.return_value = False
        app, _ = _make_app(svc)
        assert TestClient(app).delete("/api/eval/qa-pairs/qa-1").status_code == 404

    def test_batch_status_200(self):
        app, svc = _make_app()
        resp = TestClient(app).post("/api/eval/qa-pairs/batch-status", json={"qa_ids": ["qa-1"], "status": "approved"})
        assert resp.status_code == 200
        svc.batch_update_status.assert_called_once()


class TestGenerate:
    def test_200(self):
        app, _ = _make_app()
        resp = TestClient(app).post("/api/eval/generate", json={"count": 5})
        assert resp.status_code == 200


class TestEvalRuns:
    def test_run_200(self):
        app, _ = _make_app()
        assert TestClient(app).post("/api/eval/run").status_code == 200

    def test_list_runs_200(self):
        app, _ = _make_app()
        assert TestClient(app).get("/api/eval/runs").status_code == 200

    def test_get_run_404(self):
        app, _ = _make_app()
        assert TestClient(app).get("/api/eval/runs/nonexistent").status_code == 404

    def test_get_run_200(self):
        svc = MagicMock()
        svc.get_eval_run.return_value = {"run_id": "run-1", "scores": {}}
        app, _ = _make_app(svc)
        assert TestClient(app).get("/api/eval/runs/run-1").status_code == 200
