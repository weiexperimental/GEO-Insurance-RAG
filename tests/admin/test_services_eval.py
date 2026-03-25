"""Tests for admin.backend.services.eval.EvalService"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from opensearchpy import NotFoundError

from admin.backend.services.eval import EvalService, QA_INDEX, RUNS_INDEX


def _search_response(hits, total=None):
    return {
        "hits": {
            "total": {"value": total if total is not None else len(hits)},
            "hits": hits,
        }
    }


def _make_qa_hit(qa_id="qa-abc", question="test?", expected="answer", status="approved"):
    return {
        "_id": qa_id,
        "_source": {
            "question": question,
            "expected_answer": expected,
            "source_doc": "test.pdf",
            "category": "product_detail",
            "difficulty": "simple",
            "status": status,
            "created_by": "manual",
            "created_at": 1000,
            "updated_at": 1000,
        },
    }


class TestListQAPairs:
    def test_returns_pairs_with_total(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([_make_qa_hit()])
        svc = EvalService(os_client=os_client)
        result = svc.list_qa_pairs(None, None, None, 1, 20)
        assert len(result["pairs"]) == 1
        assert result["total"] == 1

    def test_filters_by_status(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([])
        svc = EvalService(os_client=os_client)
        svc.list_qa_pairs(None, "approved", None, 1, 20)
        body = os_client.search.call_args[1]["body"]
        must = body["query"]["bool"]["must"]
        assert any("term" in c and "status" in c.get("term", {}) for c in must)


class TestCreateQAPair:
    def test_indexes_with_correct_status(self):
        os_client = MagicMock()
        svc = EvalService(os_client=os_client)
        result = svc.create_qa_pair("question?", "answer", "doc.pdf", "pricing")
        os_client.index.assert_called_once()
        call_kwargs = os_client.index.call_args[1]
        assert call_kwargs["index"] == QA_INDEX
        assert call_kwargs["body"]["status"] == "approved"
        assert call_kwargs["body"]["created_by"] == "manual"
        assert result["question"] == "question?"


class TestUpdateQAPair:
    def test_updates_allowed_fields(self):
        os_client = MagicMock()
        svc = EvalService(os_client=os_client)
        svc.update_qa_pair("qa-1", {"question": "new?", "status": "rejected"})
        os_client.update.assert_called_once()
        doc = os_client.update.call_args[1]["body"]["doc"]
        assert doc["question"] == "new?"
        assert doc["status"] == "rejected"
        assert "updated_at" in doc

    def test_filters_disallowed_fields(self):
        os_client = MagicMock()
        svc = EvalService(os_client=os_client)
        svc.update_qa_pair("qa-1", {"question": "new?", "hacker_field": "bad"})
        doc = os_client.update.call_args[1]["body"]["doc"]
        assert "hacker_field" not in doc


class TestDeleteQAPair:
    def test_returns_true_on_success(self):
        os_client = MagicMock()
        svc = EvalService(os_client=os_client)
        assert svc.delete_qa_pair("qa-1") is True

    def test_returns_false_on_not_found(self):
        os_client = MagicMock()
        os_client.delete.side_effect = NotFoundError(404, "not found", {})
        svc = EvalService(os_client=os_client)
        assert svc.delete_qa_pair("qa-1") is False


class TestBatchUpdateStatus:
    def test_updates_count(self):
        os_client = MagicMock()
        svc = EvalService(os_client=os_client)
        result = svc.batch_update_status(["qa-1", "qa-2"], "approved")
        assert result["updated"] == 2
        assert os_client.update.call_count == 2


class TestListEvalRuns:
    def test_returns_runs(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([{
            "_id": "run-1",
            "_source": {"timestamp": 1000, "total_pairs": 10, "scores": {}, "status": "completed"},
        }])
        svc = EvalService(os_client=os_client)
        runs = svc.list_eval_runs()
        assert len(runs) == 1
        assert runs[0]["run_id"] == "run-1"


class TestGetEvalRun:
    def test_returns_run(self):
        os_client = MagicMock()
        os_client.get.return_value = {
            "_id": "run-1",
            "_source": {"timestamp": 1000, "total_pairs": 10, "scores": {}, "results": [], "status": "completed"},
        }
        svc = EvalService(os_client=os_client)
        run = svc.get_eval_run("run-1")
        assert run["run_id"] == "run-1"

    def test_returns_none_on_not_found(self):
        os_client = MagicMock()
        os_client.get.side_effect = NotFoundError(404, "not found", {})
        svc = EvalService(os_client=os_client)
        assert svc.get_eval_run("nonexistent") is None


class TestGenerateQAPairs:
    @pytest.mark.asyncio
    async def test_returns_error_without_llm(self):
        svc = EvalService(os_client=MagicMock())
        result = await svc.generate_qa_pairs(None, 5)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_generates_and_saves_drafts(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([{
            "_id": "chunk-1",
            "_source": {"content": "保障期25年", "file_path": "test.pdf", "original_type": "text"},
        }])

        async def mock_llm(prompt):
            return '[{"question": "保障期幾長?", "expected_answer": "25年", "difficulty": "simple", "category": "product_detail"}]'

        svc = EvalService(os_client=os_client, llm_func=mock_llm)
        result = await svc.generate_qa_pairs(None, 1)
        assert result["generated"] == 1
        os_client.index.assert_called_once()
        call_kwargs = os_client.index.call_args[1]
        assert call_kwargs["body"]["status"] == "draft"


class TestRunEvaluation:
    @pytest.mark.asyncio
    async def test_returns_error_without_lr(self):
        svc = EvalService(os_client=MagicMock())
        result = await svc.run_evaluation()
        assert "error" in result
