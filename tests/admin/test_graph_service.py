"""Tests for admin.backend.services.graph.GraphService"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from admin.backend.services.graph import GraphService, NOISE_TYPES, _jaccard_tokens, _similarity_reason


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node_hit(entity_id: str, entity_type: str = "保險公司", description: str = "desc") -> dict:
    return {
        "_id": entity_id,
        "_source": {
            "entity_type": entity_type,
            "description": description,
            "file_path": "data/test.pdf",
            "source_ids": ["chunk-1"],
        },
    }


def _make_edge_hit(edge_id: str, src: str, tgt: str, weight: float = 1.0) -> dict:
    return {
        "_id": edge_id,
        "_source": {
            "source_node_id": src,
            "target_node_id": tgt,
            "weight": weight,
            "description": "edge-desc",
            "keywords": "kw1,kw2",
            "file_path": "data/test.pdf",
            "source_ids": ["chunk-1"],
        },
    }


def _search_response(hits: list[dict], total: int | None = None) -> dict:
    return {
        "hits": {
            "total": {"value": total if total is not None else len(hits)},
            "hits": hits,
        }
    }


def _make_service(node_hits=None, edge_hits=None, get_resp=None) -> GraphService:
    """Return a GraphService backed by a MagicMock OpenSearch client."""
    os_client = MagicMock()

    # Default search side_effect: first call = nodes, second call = edges
    node_hits = node_hits or []
    edge_hits = edge_hits or []

    os_client.search.side_effect = [
        _search_response(node_hits),
        _search_response(edge_hits),
    ]

    if get_resp is not None:
        os_client.get.return_value = get_resp

    return GraphService(os_client=os_client)


# ---------------------------------------------------------------------------
# get_graph
# ---------------------------------------------------------------------------

class TestGetGraph:
    def test_returns_nodes_and_edges_keys(self):
        svc = _make_service()
        result = svc.get_graph()
        assert "nodes" in result
        assert "edges" in result

    def test_nodes_are_mapped_correctly(self):
        hits = [_make_node_hit("AIA", "保險公司")]
        svc = _make_service(node_hits=hits)
        result = svc.get_graph()
        assert len(result["nodes"]) == 1
        node = result["nodes"][0]
        assert node["id"] == "AIA"
        assert node["entity_type"] == "保險公司"
        assert node["description"] == "desc"

    def test_edges_only_included_when_both_ends_in_nodes(self):
        node_hits = [_make_node_hit("A"), _make_node_hit("B")]
        # Edge A->B should be included; edge A->C should be excluded (C not in nodes)
        edge_hits = [
            _make_edge_hit("e1", "A", "B"),
            _make_edge_hit("e2", "A", "C"),
        ]
        svc = _make_service(node_hits=node_hits, edge_hits=edge_hits)
        result = svc.get_graph()
        assert len(result["edges"]) == 1
        assert result["edges"][0]["id"] == "e1"

    def test_empty_nodes_returns_empty_edges_without_second_search(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([])
        svc = GraphService(os_client=os_client)
        result = svc.get_graph()
        assert result == {"nodes": [], "edges": []}
        # Only one search call (nodes); no edges query needed
        assert os_client.search.call_count == 1

    def test_type_filter_uses_terms_clause(self):
        os_client = MagicMock()
        os_client.search.side_effect = [
            _search_response([_make_node_hit("X", "保單")]),
            _search_response([]),
        ]
        svc = GraphService(os_client=os_client)
        svc.get_graph(type_filter="保單")

        node_query = os_client.search.call_args_list[0][1]["body"]["query"]
        filter_clause = node_query["bool"]["filter"]
        assert any("terms" in c and "entity_type" in c["terms"] for c in filter_clause)

    def test_no_type_filter_excludes_noise_types(self):
        os_client = MagicMock()
        os_client.search.side_effect = [
            _search_response([]),
        ]
        svc = GraphService(os_client=os_client)
        svc.get_graph()

        node_query = os_client.search.call_args_list[0][1]["body"]["query"]
        must_not = node_query["bool"]["must_not"]
        noise_terms = must_not[0]["terms"]["entity_type"]
        assert set(noise_terms) == NOISE_TYPES

    def test_doc_filter_adds_match_clause(self):
        os_client = MagicMock()
        os_client.search.side_effect = [
            _search_response([]),
        ]
        svc = GraphService(os_client=os_client)
        svc.get_graph(doc_filter="data/policy.pdf")

        node_query = os_client.search.call_args_list[0][1]["body"]["query"]
        must = node_query["bool"]["must"]
        assert any("match" in c and "file_path" in c["match"] for c in must)

    def test_max_nodes_respected(self):
        os_client = MagicMock()
        os_client.search.side_effect = [_search_response([])]
        svc = GraphService(os_client=os_client)
        svc.get_graph(max_nodes=50)

        body = os_client.search.call_args_list[0][1]["body"]
        assert body["size"] == 50


# ---------------------------------------------------------------------------
# search_entities
# ---------------------------------------------------------------------------

class TestSearchEntities:
    def test_returns_list_of_dicts(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([_make_node_hit("AIA")])
        svc = GraphService(os_client=os_client)
        result = svc.search_entities("AIA")
        assert isinstance(result, list)
        assert result[0]["id"] == "AIA"

    def test_result_contains_required_fields(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([_make_node_hit("AIA", "保險公司", "big insurer")])
        svc = GraphService(os_client=os_client)
        result = svc.search_entities("AIA")
        item = result[0]
        assert "id" in item
        assert "entity_type" in item
        assert "description" in item

    def test_limit_is_passed_to_opensearch(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([])
        svc = GraphService(os_client=os_client)
        svc.search_entities("test", limit=5)
        body = os_client.search.call_args[1]["body"]
        assert body["size"] == 5

    def test_empty_results_returns_empty_list(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([])
        svc = GraphService(os_client=os_client)
        assert svc.search_entities("nonexistent") == []


# ---------------------------------------------------------------------------
# get_popular_entities
# ---------------------------------------------------------------------------

class TestGetPopularEntities:
    def test_returns_id_and_entity_type(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([_make_node_hit("AIA", "保險公司")])
        svc = GraphService(os_client=os_client)
        result = svc.get_popular_entities()
        assert result[0]["id"] == "AIA"
        assert result[0]["entity_type"] == "保險公司"

    def test_excludes_noise_types(self):
        os_client = MagicMock()
        os_client.search.return_value = _search_response([])
        svc = GraphService(os_client=os_client)
        svc.get_popular_entities()
        body = os_client.search.call_args[1]["body"]
        must_not = body["query"]["bool"]["must_not"]
        noise_terms = must_not[0]["terms"]["entity_type"]
        assert set(noise_terms) == NOISE_TYPES


# ---------------------------------------------------------------------------
# get_entity_detail
# ---------------------------------------------------------------------------

class TestGetEntityDetail:
    def _make_get_resp(self, entity_id: str) -> dict:
        return {
            "_id": entity_id,
            "_source": {
                "entity_type": "保險公司",
                "description": "A big insurer",
                "file_path": "data/test.pdf",
                "source_ids": ["chunk-1"],
            },
        }

    def test_returns_entity_and_connections_keys(self):
        entity_id = "AIA"
        os_client = MagicMock()
        os_client.get.return_value = self._make_get_resp(entity_id)
        os_client.search.return_value = _search_response([])
        svc = GraphService(os_client=os_client)
        result = svc.get_entity_detail(entity_id)
        assert "entity" in result
        assert "connections" in result

    def test_entity_has_correct_id(self):
        entity_id = "AIA"
        os_client = MagicMock()
        os_client.get.return_value = self._make_get_resp(entity_id)
        os_client.search.return_value = _search_response([])
        svc = GraphService(os_client=os_client)
        result = svc.get_entity_detail(entity_id)
        assert result["entity"]["id"] == entity_id

    def test_connections_include_direction(self):
        entity_id = "AIA"
        os_client = MagicMock()
        os_client.get.return_value = self._make_get_resp(entity_id)
        # AIA -> BUPA (outgoing), CHUBB -> AIA (incoming)
        edge_hits = [
            _make_edge_hit("e1", "AIA", "BUPA"),
            _make_edge_hit("e2", "CHUBB", "AIA"),
        ]
        os_client.search.return_value = _search_response(edge_hits)
        svc = GraphService(os_client=os_client)
        result = svc.get_entity_detail(entity_id)

        directions = {c["other_entity"]: c["direction"] for c in result["connections"]}
        assert directions["BUPA"] == "outgoing"
        assert directions["CHUBB"] == "incoming"

    def test_returns_empty_entity_on_missing(self):
        os_client = MagicMock()
        os_client.get.side_effect = Exception("Not Found")
        svc = GraphService(os_client=os_client)
        result = svc.get_entity_detail("NONEXISTENT")
        assert result["entity"] is None
        assert result["connections"] == []


# ---------------------------------------------------------------------------
# Write methods — no LightRAG
# ---------------------------------------------------------------------------

class TestWriteMethodsNoLightRAG:
    @pytest.mark.asyncio
    async def test_edit_entity_returns_error_without_lr(self):
        svc = GraphService(os_client=MagicMock())
        result = await svc.edit_entity("AIA", {"description": "new"})
        assert result == {"error": "LightRAG not initialized"}

    @pytest.mark.asyncio
    async def test_delete_entity_returns_error_without_lr(self):
        svc = GraphService(os_client=MagicMock())
        result = await svc.delete_entity("AIA")
        assert result == {"error": "LightRAG not initialized"}

    @pytest.mark.asyncio
    async def test_merge_entities_returns_error_without_lr(self):
        svc = GraphService(os_client=MagicMock())
        result = await svc.merge_entities(["A", "B"], "C")
        assert result == {"error": "LightRAG not initialized"}

    @pytest.mark.asyncio
    async def test_edit_relation_returns_error_without_lr(self):
        svc = GraphService(os_client=MagicMock())
        result = await svc.edit_relation("A", "B", {"weight": 2.0})
        assert result == {"error": "LightRAG not initialized"}

    @pytest.mark.asyncio
    async def test_delete_relation_returns_error_without_lr(self):
        svc = GraphService(os_client=MagicMock())
        result = await svc.delete_relation("A", "B")
        assert result == {"error": "LightRAG not initialized"}


# ---------------------------------------------------------------------------
# Write methods — with LightRAG mock
# ---------------------------------------------------------------------------

class TestWriteMethodsWithLightRAG:
    def _make_svc_with_lr(self) -> tuple[GraphService, MagicMock]:
        lr = MagicMock()
        lr.edit_entity = AsyncMock(return_value={"status": "ok"})
        lr.delete_by_entity = AsyncMock(return_value={"status": "ok"})
        lr.merge_entities = AsyncMock(return_value={"status": "ok"})
        lr.edit_relation = AsyncMock(return_value={"status": "ok"})
        lr.delete_by_relation = AsyncMock(return_value={"status": "ok"})
        svc = GraphService(os_client=MagicMock(), lightrag=lr)
        return svc, lr

    @pytest.mark.asyncio
    async def test_edit_entity_delegates_to_lr(self):
        svc, lr = self._make_svc_with_lr()
        result = await svc.edit_entity("AIA", {"description": "updated"})
        lr.edit_entity.assert_called_once_with("AIA", {"description": "updated"})
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_delete_entity_delegates_to_lr(self):
        svc, lr = self._make_svc_with_lr()
        await svc.delete_entity("AIA")
        lr.delete_by_entity.assert_called_once_with("AIA")

    @pytest.mark.asyncio
    async def test_merge_entities_delegates_to_lr(self):
        svc, lr = self._make_svc_with_lr()
        await svc.merge_entities(["A", "B"], "C")
        lr.merge_entities.assert_called_once_with(["A", "B"], "C")

    @pytest.mark.asyncio
    async def test_edit_relation_delegates_to_lr(self):
        svc, lr = self._make_svc_with_lr()
        await svc.edit_relation("A", "B", {"weight": 0.5})
        lr.edit_relation.assert_called_once_with("A", "B", {"weight": 0.5})

    @pytest.mark.asyncio
    async def test_delete_relation_delegates_to_lr(self):
        svc, lr = self._make_svc_with_lr()
        await svc.delete_relation("A", "B")
        lr.delete_by_relation.assert_called_once_with("A", "B")


# ---------------------------------------------------------------------------
# _jaccard_tokens helper
# ---------------------------------------------------------------------------

class TestJaccardTokens:
    def test_identical_strings_return_one(self):
        assert _jaccard_tokens("AIA", "AIA") == 1.0

    def test_completely_different_returns_zero(self):
        assert _jaccard_tokens("AIA", "XYZ") == 0.0

    def test_partial_overlap(self):
        score = _jaccard_tokens("AIA Life", "AIA Insurance")
        assert 0.0 < score < 1.0

    def test_empty_string_returns_zero(self):
        assert _jaccard_tokens("", "AIA") == 0.0
        assert _jaccard_tokens("AIA", "") == 0.0

    def test_cjk_characters_treated_as_tokens(self):
        # 立橋 shares 橋 with 立橋人壽
        score = _jaccard_tokens("立橋", "立橋人壽")
        assert score > 0.0


# ---------------------------------------------------------------------------
# _similarity_reason helper
# ---------------------------------------------------------------------------

class TestSimilarityReason:
    def test_embedding_similarity_fallback(self):
        reason = _similarity_reason("AIA", "BUPA", 0.1, 0.5)
        assert reason == "embedding similarity"

    def test_similar_name_threshold(self):
        # name_sim > 0.5 → "similar name"
        reason = _similarity_reason("AIA Life", "AIA", 0.6, 0.5)
        assert "similar name" in reason

    def test_very_similar_name_threshold(self):
        reason = _similarity_reason("AIA Life", "AIA", 0.9, 0.5)
        assert "very similar name" in reason

    def test_high_vector_score(self):
        reason = _similarity_reason("AIA", "BUPA", 0.1, 0.95)
        assert "similar description" in reason

    def test_substring_match(self):
        reason = _similarity_reason("立橋", "立橋人壽保險", 0.2, 0.5)
        assert "substring match" in reason


# ---------------------------------------------------------------------------
# find_similar_entities
# ---------------------------------------------------------------------------

class TestFindSimilarEntities:
    def test_returns_similar_entities(self):
        os_client = MagicMock()
        # Mock get (source entity)
        os_client.get.return_value = {
            "_id": "ent-1",
            "_source": {
                "entity_name": "立橋人壽",
                "content": "insurance company",
                "vector": [0.1] * 3072,
                "file_path": "test.pdf",
            },
        }
        # Mock KNN search
        os_client.search.return_value = _search_response([
            {
                "_id": "ent-1",  # self - should be filtered
                "_score": 1.0,
                "_source": {"entity_name": "立橋人壽", "content": "same", "file_path": "test.pdf"},
            },
            {
                "_id": "ent-2",
                "_score": 0.95,
                "_source": {"entity_name": "立橋人壽保險有限公司", "content": "full name", "file_path": "test.pdf"},
            },
            {
                "_id": "ent-3",
                "_score": 0.85,
                "_source": {"entity_name": "Well Link Life", "content": "english name", "file_path": "test.pdf"},
            },
        ])
        svc = GraphService(os_client=os_client)
        results = svc.find_similar_entities("ent-1", limit=5)

        assert len(results) == 2  # self filtered out
        assert results[0]["entity_id"] == "ent-2"
        assert results[0]["vector_similarity"] == 0.95
        assert "substring match" in results[0]["reason"]

    def test_returns_empty_when_entity_not_found(self):
        os_client = MagicMock()
        os_client.get.side_effect = Exception("Not found")
        svc = GraphService(os_client=os_client)
        assert svc.find_similar_entities("nonexistent") == []

    def test_returns_empty_when_no_vector(self):
        os_client = MagicMock()
        os_client.get.return_value = {
            "_id": "ent-1",
            "_source": {"entity_name": "test", "content": "no vector"},
        }
        svc = GraphService(os_client=os_client)
        assert svc.find_similar_entities("ent-1") == []

    def test_result_fields_are_present(self):
        os_client = MagicMock()
        os_client.get.return_value = {
            "_id": "ent-1",
            "_source": {
                "entity_name": "AIA",
                "content": "insurer",
                "vector": [0.1] * 3072,
                "file_path": "test.pdf",
            },
        }
        os_client.search.return_value = _search_response([
            {
                "_id": "ent-2",
                "_score": 0.88,
                "_source": {"entity_name": "AIA Life", "content": "AIA subsidiary", "file_path": "test.pdf"},
            },
        ])
        svc = GraphService(os_client=os_client)
        results = svc.find_similar_entities("ent-1")

        assert len(results) == 1
        r = results[0]
        assert r["entity_id"] == "ent-2"
        assert r["entity_name"] == "AIA Life"
        assert "description" in r
        assert "file_path" in r
        assert "vector_similarity" in r
        assert "name_similarity" in r
        assert "reason" in r

    def test_description_truncated_to_200_chars(self):
        os_client = MagicMock()
        long_content = "x" * 500
        os_client.get.return_value = {
            "_id": "ent-1",
            "_source": {
                "entity_name": "AIA",
                "content": "short",
                "vector": [0.1] * 3072,
                "file_path": "test.pdf",
            },
        }
        os_client.search.return_value = _search_response([
            {
                "_id": "ent-2",
                "_score": 0.8,
                "_source": {"entity_name": "BUPA", "content": long_content, "file_path": "test.pdf"},
            },
        ])
        svc = GraphService(os_client=os_client)
        results = svc.find_similar_entities("ent-1")
        assert len(results[0]["description"]) <= 200

    def test_limit_respected(self):
        os_client = MagicMock()
        os_client.get.return_value = {
            "_id": "ent-1",
            "_source": {
                "entity_name": "AIA",
                "content": "insurer",
                "vector": [0.1] * 3072,
                "file_path": "test.pdf",
            },
        }
        # Return 10 hits (not self), but ask for limit=3
        hits = [
            {
                "_id": f"ent-{i}",
                "_score": 0.9 - i * 0.01,
                "_source": {"entity_name": f"Entity {i}", "content": "desc", "file_path": "test.pdf"},
            }
            for i in range(2, 12)
        ]
        os_client.search.return_value = _search_response(hits)
        svc = GraphService(os_client=os_client)
        results = svc.find_similar_entities("ent-1", limit=3)
        assert len(results) == 3

    def test_search_exception_returns_empty(self):
        os_client = MagicMock()
        os_client.get.return_value = {
            "_id": "ent-1",
            "_source": {
                "entity_name": "AIA",
                "content": "insurer",
                "vector": [0.1] * 3072,
                "file_path": "test.pdf",
            },
        }
        os_client.search.side_effect = Exception("Search failed")
        svc = GraphService(os_client=os_client)
        assert svc.find_similar_entities("ent-1") == []
