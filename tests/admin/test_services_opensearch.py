from unittest.mock import MagicMock, patch
import pytest

from admin.backend.services.opensearch import OpenSearchService


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def service(mock_client):
    return OpenSearchService(mock_client)


# ---------------------------------------------------------------------------
# get_cluster_health
# ---------------------------------------------------------------------------

def test_get_cluster_health(service, mock_client):
    mock_client.cluster.health.return_value = {"status": "green", "number_of_nodes": 1}
    result = service.get_cluster_health()
    mock_client.cluster.health.assert_called_once()
    assert result["status"] == "green"
    assert result["number_of_nodes"] == 1


# ---------------------------------------------------------------------------
# get_node_stats
# ---------------------------------------------------------------------------

def test_get_node_stats(service, mock_client):
    mock_client.nodes.stats.return_value = {"nodes": {"abc": {"jvm": {}}}}
    result = service.get_node_stats()
    mock_client.nodes.stats.assert_called_once_with(metric="jvm,fs,os")
    assert "nodes" in result


# ---------------------------------------------------------------------------
# get_index_stats
# ---------------------------------------------------------------------------

def test_get_index_stats(service, mock_client):
    mock_client.cat.indices.return_value = [
        {"index": "doc_status", "docs.count": "18", "pri.store.size": "500k"},
    ]
    result = service.get_index_stats()
    mock_client.cat.indices.assert_called_once_with(
        format="json",
        h="index,health,docs.count,docs.deleted,store.size,pri.store.size",
    )
    assert len(result) == 1
    assert result[0]["index"] == "doc_status"


# ---------------------------------------------------------------------------
# get_doc_count
# ---------------------------------------------------------------------------

def test_get_doc_count(service, mock_client):
    mock_client.count.return_value = {"count": 42}
    result = service.get_doc_count("doc_status")
    mock_client.count.assert_called_once_with(index="doc_status")
    assert result == 42


# ---------------------------------------------------------------------------
# get_knn_stats
# ---------------------------------------------------------------------------

def test_get_knn_stats(service, mock_client):
    mock_client.transport.perform_request.return_value = {"knn_query_requests": 100}
    result = service.get_knn_stats()
    mock_client.transport.perform_request.assert_called_once_with("GET", "/_plugins/_knn/stats")
    assert "knn_query_requests" in result


# ---------------------------------------------------------------------------
# get_ingestion_statuses — no filter
# ---------------------------------------------------------------------------

def test_get_ingestion_statuses_no_filter(service, mock_client):
    mock_client.search.return_value = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                {
                    "_id": "doc1",
                    "_source": {
                        "status": "processed",
                        "file_path": "/inbox/a.pdf",
                        "metadata": {"file_name": "a.pdf", "company": "AIA"},
                        "chunks_count": 10,
                        "created_at": "2026-03-24T00:00:00",
                        "updated_at": "2026-03-24T01:00:00",
                    },
                },
                {
                    "_id": "doc2",
                    "_source": {
                        "status": "failed",
                        "file_path": "/inbox/b.pdf",
                        "metadata": {"file_name": "b.pdf"},
                        "chunks_count": None,
                        "created_at": "2026-03-24T00:00:00",
                        "updated_at": "2026-03-24T01:00:00",
                    },
                },
            ],
        }
    }
    result = service.get_ingestion_statuses(limit=10, offset=0)
    assert result["total"] == 2
    assert len(result["documents"]) == 2
    assert result["documents"][0]["document_id"] == "doc1"
    assert result["documents"][0]["status"] == "processed"
    assert result["documents"][0]["file_name"] == "a.pdf"
    assert result["documents"][0]["metadata"]["company"] == "AIA"

    call_kwargs = mock_client.search.call_args[1]
    assert call_kwargs["index"] == "doc_status"
    call_body = call_kwargs["body"]
    assert call_body["query"] == {"match_all": {}}
    assert call_body["size"] == 10
    assert call_body["from"] == 0


def test_get_ingestion_statuses_with_filter(service, mock_client):
    mock_client.search.return_value = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "doc3",
                    "_source": {
                        "status": "pending",
                        "file_path": "/inbox/c.pdf",
                        "metadata": {"file_name": "c.pdf"},
                        "chunks_count": None,
                        "created_at": "2026-03-24T00:00:00",
                        "updated_at": "2026-03-24T00:00:00",
                    },
                },
            ],
        }
    }
    result = service.get_ingestion_statuses(limit=5, offset=0, status_filter="pending")
    assert result["total"] == 1
    assert result["documents"][0]["status"] == "pending"

    call_body = mock_client.search.call_args[1]["body"]
    assert call_body["query"] == {"term": {"status": "pending"}}


def test_get_ingestion_statuses_pagination(service, mock_client):
    mock_client.search.return_value = {
        "hits": {"total": {"value": 100}, "hits": []}
    }
    service.get_ingestion_statuses(limit=20, offset=40)
    call_body = mock_client.search.call_args[1]["body"]
    assert call_body["size"] == 20
    assert call_body["from"] == 40


def test_get_ingestion_statuses_sort(service, mock_client):
    mock_client.search.return_value = {
        "hits": {"total": {"value": 0}, "hits": []}
    }
    service.get_ingestion_statuses(sort_field="file_path", sort_order="asc")
    call_body = mock_client.search.call_args[1]["body"]
    assert call_body["sort"] == [{"file_path": {"order": "asc"}}]


def test_get_ingestion_statuses_default_sort_is_updated_at(service, mock_client):
    mock_client.search.return_value = {
        "hits": {"total": {"value": 0}, "hits": []}
    }
    service.get_ingestion_statuses()
    call_body = mock_client.search.call_args[1]["body"]
    assert call_body["sort"] == [{"updated_at": {"order": "desc"}}]


def test_get_ingestion_statuses_file_name_falls_back_to_path_basename(service, mock_client):
    """If metadata has no file_name, derive it from file_path."""
    mock_client.search.return_value = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "doc99",
                    "_source": {
                        "status": "processed",
                        "file_path": "/inbox/some_doc.pdf",
                        "metadata": {},
                        "chunks_count": 5,
                        "created_at": "2026-03-24T00:00:00",
                        "updated_at": "2026-03-24T01:00:00",
                    },
                }
            ],
        }
    }
    result = service.get_ingestion_statuses()
    assert result["documents"][0]["file_name"] == "some_doc.pdf"


def test_get_ingestion_statuses_file_name_falls_back_to_id(service, mock_client):
    """If metadata and file_path are both empty, fall back to _id."""
    mock_client.search.return_value = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "fallback-id",
                    "_source": {
                        "status": "pending",
                        "file_path": "",
                        "metadata": {},
                        "chunks_count": None,
                        "created_at": "2026-03-24T00:00:00",
                        "updated_at": "2026-03-24T00:00:00",
                    },
                }
            ],
        }
    }
    result = service.get_ingestion_statuses()
    assert result["documents"][0]["file_name"] == "fallback-id"


# ---------------------------------------------------------------------------
# get_active_ingestions
# ---------------------------------------------------------------------------

def test_get_active_ingestions(service, mock_client):
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "doc5",
                    "_source": {
                        "status": "processing",
                        "file_path": "/inbox/e.pdf",
                        "metadata": {"file_name": "e.pdf"},
                        "chunks_count": None,
                        "created_at": "2026-03-24T00:00:00",
                        "updated_at": "2026-03-24T00:00:00",
                    },
                },
            ]
        }
    }
    result = service.get_active_ingestions()
    assert len(result) == 1
    assert result[0]["document_id"] == "doc5"
    assert result[0]["status"] == "processing"

    call_kwargs = mock_client.search.call_args[1]
    assert call_kwargs["index"] == "doc_status"
    call_body = call_kwargs["body"]
    must = call_body["query"]["bool"]["must"]
    assert {"terms": {"status": ["pending", "processing"]}} in must


def test_get_active_ingestions_empty(service, mock_client):
    mock_client.search.return_value = {"hits": {"hits": []}}
    result = service.get_active_ingestions()
    assert result == []


# ---------------------------------------------------------------------------
# get_ingestion_analytics
# ---------------------------------------------------------------------------

def test_get_ingestion_analytics(service, mock_client):
    mock_client.search.return_value = {
        "aggregations": {
            "status_counts": {
                "buckets": [
                    {"key": "processed", "doc_count": 10},
                    {"key": "failed", "doc_count": 2},
                    {"key": "pending", "doc_count": 3},
                ]
            }
        }
    }
    result = service.get_ingestion_analytics()
    assert result["status_counts"]["processed"] == 10
    assert result["status_counts"]["failed"] == 2
    assert result["status_counts"]["pending"] == 3

    call_kwargs = mock_client.search.call_args[1]
    assert call_kwargs["index"] == "doc_status"


# ---------------------------------------------------------------------------
# save_query_history
# ---------------------------------------------------------------------------

def test_save_query_history(service, mock_client):
    entry = {"query": "What is the deductible?", "timestamp": "2026-03-23T10:00:00"}
    service.save_query_history(entry)
    mock_client.index.assert_called_once_with(index="rag-query-history", body=entry)


# ---------------------------------------------------------------------------
# get_query_history
# ---------------------------------------------------------------------------

def test_get_query_history(service, mock_client):
    mock_client.search.return_value = {
        "hits": {
            "hits": [
                {"_source": {"query": "test query", "timestamp": "2026-03-23T10:00:00"}},
            ]
        }
    }
    result = service.get_query_history(limit=10)
    assert len(result) == 1
    assert result[0]["query"] == "test query"
    mock_client.search.assert_called_once()


def test_get_query_history_returns_empty_on_error(service, mock_client):
    mock_client.search.side_effect = Exception("Index not found")
    result = service.get_query_history()
    assert result == []


# ---------------------------------------------------------------------------
# get_system_overview
# ---------------------------------------------------------------------------

def _make_overview_mocks(mock_client):
    """Set up mock_client with consistent return values for get_system_overview."""
    mock_client.cluster.health.return_value = {"status": "green"}
    mock_client.cat.indices.return_value = [
        {"index": "doc_status", "docs.count": "18", "pri.store.size": "500000b"},
        {"index": "chunk_entity_relation-nodes", "docs.count": "865", "pri.store.size": "2000000b"},
        {"index": "chunk_entity_relation-edges", "docs.count": "1725", "pri.store.size": "3000000b"},
        {"index": "chunks", "docs.count": "400", "pri.store.size": "1000000b"},
        {"index": "llm_response_cache", "docs.count": "303", "pri.store.size": "100000b"},
    ]
    mock_client.search.return_value = {
        "aggregations": {
            "status_counts": {
                "buckets": [
                    {"key": "processed", "doc_count": 15},
                    {"key": "failed", "doc_count": 2},
                    {"key": "pending", "doc_count": 1},
                ]
            }
        }
    }


def test_get_system_overview_cluster_status(service, mock_client):
    _make_overview_mocks(mock_client)
    result = service.get_system_overview()
    assert result["cluster_status"] == "green"


def test_get_system_overview_document_counts(service, mock_client):
    _make_overview_mocks(mock_client)
    result = service.get_system_overview()
    assert result["documents"] == "18"
    assert result["entities"] == "865"
    assert result["relationships"] == "1725"
    assert result["chunks"] == "400"
    assert result["llm_cache"] == "303"


def test_get_system_overview_pending_and_failed(service, mock_client):
    _make_overview_mocks(mock_client)
    result = service.get_system_overview()
    # pending = pending(1) + processing(0)
    assert result["pending"] == "1"
    assert result["failed"] == "2"


def test_get_system_overview_index_size(service, mock_client):
    _make_overview_mocks(mock_client)
    result = service.get_system_overview()
    # total_bytes = 500000 + 2000000 + 3000000 + 1000000 + 100000 = 6600000 bytes => 6.6MB
    assert "MB" in result["index_size"] or "GB" in result["index_size"]


def test_get_system_overview_total_indices(service, mock_client):
    _make_overview_mocks(mock_client)
    result = service.get_system_overview()
    assert result["total_indices"] == 5
    assert len(result["indices"]) == 5


def test_get_system_overview_missing_index_returns_zero(service, mock_client):
    """Indices not present in cat.indices should default to '0'."""
    mock_client.cluster.health.return_value = {"status": "yellow"}
    mock_client.cat.indices.return_value = []
    mock_client.search.return_value = {
        "aggregations": {"status_counts": {"buckets": []}}
    }
    result = service.get_system_overview()
    assert result["documents"] == "0"
    assert result["entities"] == "0"
    assert result["chunks"] == "0"
    assert result["total_indices"] == 0
