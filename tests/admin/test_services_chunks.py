"""Tests for admin.backend.services.chunks.ChunkService"""
import pytest
from unittest.mock import MagicMock
from opensearchpy import NotFoundError

from admin.backend.services.chunks import ChunkService, NOISE_TYPES


def _make_chunk(content="Some insurance content here", tokens=150,
                original_type="text", **overrides):
    return {"content": content, "tokens": tokens, "original_type": original_type, **overrides}


def _search_response(hits, total=None):
    return {
        "hits": {
            "total": {"value": total if total is not None else len(hits)},
            "hits": hits,
        }
    }


def _make_hit(chunk_id="chunk-abc", **chunk_fields):
    return {"_id": chunk_id, "_source": _make_chunk(**chunk_fields)}


class TestAssessQuality:
    def _svc(self):
        return ChunkService(os_client=MagicMock())

    def test_good_chunk(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(tokens=200))
        assert tier == "good"
        assert reasons == []

    def test_bad_footer(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(original_type="footer"))
        assert tier == "bad"
        assert "footer" in reasons

    def test_bad_header(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(original_type="header"))
        assert tier == "bad"
        assert "header" in reasons

    def test_bad_unknown(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(original_type="UNKNOWN"))
        assert tier == "bad"
        assert "UNKNOWN" in reasons

    def test_bad_empty_content(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(content="   ", tokens=0))
        assert tier == "bad"
        assert "empty" in reasons

    def test_bad_too_short(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(tokens=5))
        assert tier == "bad"
        assert any("too short" in r for r in reasons)

    def test_warning_short(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(tokens=30))
        assert tier == "warning"
        assert any("short" in r for r in reasons)

    def test_warning_too_long(self):
        tier, reasons = self._svc()._assess_quality(_make_chunk(tokens=2500))
        assert tier == "warning"
        assert any("too long" in r for r in reasons)

    def test_warning_malformed_table(self):
        tier, reasons = self._svc()._assess_quality(
            _make_chunk(content="<table><tr><td>hi</td></tr>", tokens=100)
        )
        assert tier == "warning"
        assert "malformed table" in reasons

    def test_bad_takes_precedence_over_warning(self):
        tier, _ = self._svc()._assess_quality(_make_chunk(original_type="footer", tokens=30))
        assert tier == "bad"


class TestListChunks:
    def test_returns_chunks_with_quality(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([_make_hit()])
        svc = ChunkService(os_client=os_client)
        result = svc.list_chunks(None, None, None, None, 1, 20)
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["quality"] == "good"
        assert result["total"] == 1

    def test_doc_id_filter_uses_term_query(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([])
        svc = ChunkService(os_client=os_client)
        svc.list_chunks("doc-abc", None, None, None, 1, 20)
        body = os_client.search.call_args[1]["body"]
        must = body["query"]["bool"]["must"]
        assert any("term" in c for c in must)

    def test_quality_filter_returns_correct_total(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([
            _make_hit("c1", original_type="footer", tokens=100),
            _make_hit("c2", tokens=200),
            _make_hit("c3", original_type="header", tokens=100),
        ])
        svc = ChunkService(os_client=os_client)
        result = svc.list_chunks(None, None, "bad", None, 1, 20)
        assert result["total"] == 2
        assert all(c["quality"] == "bad" for c in result["chunks"])

    def test_quality_filter_pagination(self):
        os_client = MagicMock()
        hits = [_make_hit(f"c{i}", original_type="footer", tokens=100) for i in range(5)]
        os_client.search.return_value = _search_response(hits)
        svc = ChunkService(os_client=os_client)
        result = svc.list_chunks(None, None, "bad", None, 2, 2)
        assert result["total"] == 5
        assert result["page"] == 2
        assert len(result["chunks"]) == 2


class TestGetChunk:
    def test_returns_chunk_with_quality(self):
        os_client = MagicMock()
        os_client.get.return_value = {"_id": "chunk-1", "_source": _make_chunk()}
        svc = ChunkService(os_client=os_client)
        result = svc.get_chunk("chunk-1")
        assert result["id"] == "chunk-1"
        assert result["quality"] == "good"

    def test_returns_none_for_missing(self):
        os_client = MagicMock()
        os_client.get.side_effect = NotFoundError(404, "not found", {})
        svc = ChunkService(os_client=os_client)
        assert svc.get_chunk("nonexistent") is None


class TestDeleteChunk:
    def test_deletes_from_both_indices(self):
        os_client = MagicMock()
        svc = ChunkService(os_client=os_client)
        result = svc.delete_chunk("chunk-1")
        assert result is True
        assert os_client.delete.call_count == 2
        indices = [c.kwargs["index"] for c in os_client.delete.call_args_list]
        assert "text_chunks" in indices
        assert "chunks" in indices

    def test_returns_false_when_not_found_in_either(self):
        os_client = MagicMock()
        os_client.delete.side_effect = NotFoundError(404, "not found", {})
        svc = ChunkService(os_client=os_client)
        assert svc.delete_chunk("nonexistent") is False


class TestBatchDelete:
    def test_returns_deleted_count(self):
        os_client = MagicMock()
        svc = ChunkService(os_client=os_client)
        result = svc.batch_delete(["c1", "c2", "c3"])
        assert result["deleted"] == 3
        assert result["total"] == 3


class TestUpdateChunk:
    @pytest.mark.asyncio
    async def test_updates_text_chunks_index(self):
        os_client = MagicMock()
        svc = ChunkService(os_client=os_client)
        result = await svc.update_chunk("chunk-1", "new content here")
        assert result["id"] == "chunk-1"
        assert result["content"] == "new content here"
        os_client.update.assert_called_once()
        call_kwargs = os_client.update.call_args[1]
        assert call_kwargs["index"] == "text_chunks"

    @pytest.mark.asyncio
    async def test_re_embeds_when_embed_func_provided(self):
        os_client = MagicMock()
        embed_fn = MagicMock(return_value=[[0.1]*3072])
        async def async_embed(texts):
            return embed_fn(texts)
        svc = ChunkService(os_client=os_client, embedding_func=async_embed)
        await svc.update_chunk("chunk-1", "new content")
        assert os_client.update.call_count == 2
        embed_fn.assert_called_once()


class TestGetQualityStats:
    def test_counts_tiers(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([
            _make_hit("c1", tokens=200),
            _make_hit("c2", original_type="footer"),
            _make_hit("c3", tokens=30),
        ])
        svc = ChunkService(os_client=os_client)
        stats = svc.get_quality_stats()
        assert stats == {"good": 1, "warning": 1, "bad": 1, "total": 3}

    def test_filters_by_doc_id(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([])
        svc = ChunkService(os_client=os_client)
        svc.get_quality_stats("doc-abc")
        body = os_client.search.call_args[1]["body"]
        must = body["query"]["bool"]["must"]
        assert any("term" in c for c in must)


class TestGetTokenDistribution:
    def test_returns_buckets(self):
        os_client = MagicMock()
        os_client.search.return_value = {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "token_histogram": {
                    "buckets": [
                        {"key": 0, "doc_count": 5},
                        {"key": 100, "doc_count": 10},
                        {"key": 200, "doc_count": 3},
                    ]
                }
            }
        }
        svc = ChunkService(os_client=os_client)
        result = svc.get_token_distribution()
        assert len(result["buckets"]) == 3
        assert result["buckets"][0]["range"] == "0-99"
        assert result["buckets"][0]["count"] == 5
