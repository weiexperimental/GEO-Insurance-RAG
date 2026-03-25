"""Tests for admin/backend/poller.py — Poller."""
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from admin.backend.poller import Poller
from admin.backend.services.opensearch import OpenSearchService
from admin.backend.ws import ConnectionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_os_service():
    svc = MagicMock(spec=OpenSearchService)
    svc.get_cluster_health.return_value = {"status": "green"}
    svc.get_node_stats.return_value = {"nodes": {}}
    svc.get_index_stats.return_value = []
    svc.get_system_overview.return_value = {"cluster_status": "green"}
    svc.get_knn_stats.return_value = {}
    svc.get_active_ingestions.return_value = []
    return svc


@pytest.fixture
def mock_ws_manager():
    mgr = MagicMock(spec=ConnectionManager)
    mgr.broadcast = AsyncMock()
    mgr.update_snapshot = MagicMock()
    return mgr


@pytest.fixture
def poller(mock_os_service, mock_ws_manager, tmp_path):
    return Poller(
        os_service=mock_os_service,
        ws_manager=mock_ws_manager,
        log_dir=str(tmp_path),
    )


# ---------------------------------------------------------------------------
# _compute_diff
# ---------------------------------------------------------------------------

def test_compute_diff_detects_changes(poller):
    old = {"system_health": {"cluster": {"status": "green"}}, "ingestion": {"active": []}}
    new = {"system_health": {"cluster": {"status": "yellow"}}, "ingestion": {"active": []}}
    diff = poller._compute_diff(old, new)
    assert "system_health" in diff
    assert "ingestion" not in diff


def test_compute_diff_returns_empty_when_no_change(poller):
    snapshot = {"system_health": {"cluster": {"status": "green"}}}
    diff = poller._compute_diff(snapshot, snapshot)
    assert diff == {}


def test_compute_diff_detects_new_keys(poller):
    old = {}
    new = {"ingestion": {"active": [{"doc": "a.pdf"}]}}
    diff = poller._compute_diff(old, new)
    assert "ingestion" in diff


def test_compute_diff_detects_removed_values(poller):
    # A key present in new but with a different value from old (None vs dict)
    old = {"ingestion": None}
    new = {"ingestion": {"active": []}}
    diff = poller._compute_diff(old, new)
    assert "ingestion" in diff


# ---------------------------------------------------------------------------
# poll_once — broadcasts when data changes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_once_broadcasts_on_first_call(poller, mock_ws_manager):
    """First poll always has diff (snapshot starts empty)."""
    await poller.poll_once()
    assert mock_ws_manager.broadcast.await_count >= 1
    mock_ws_manager.update_snapshot.assert_called()


@pytest.mark.asyncio
async def test_poll_once_broadcasts_system_health_type(poller, mock_ws_manager):
    await poller.poll_once()
    call_args_list = mock_ws_manager.broadcast.call_args_list
    types = [call[0][0]["type"] for call in call_args_list]
    assert "system_health" in types


@pytest.mark.asyncio
async def test_poll_once_does_not_broadcast_when_no_change(poller, mock_ws_manager):
    """After first poll, a second identical poll should not broadcast again."""
    await poller.poll_once()
    first_count = mock_ws_manager.broadcast.await_count

    # Reset broadcast mock but keep snapshot state
    mock_ws_manager.broadcast.reset_mock()

    # Second poll with identical data
    await poller.poll_once()
    assert mock_ws_manager.broadcast.await_count == 0


@pytest.mark.asyncio
async def test_poll_once_broadcasts_ingestion_update_type(poller, mock_ws_manager, mock_os_service):
    """Ingestion update should broadcast with correct type."""
    mock_os_service.get_active_ingestions.return_value = [{"document_id": "doc1", "status": "parsing"}]
    await poller.poll_once()

    call_args_list = mock_ws_manager.broadcast.call_args_list
    types = [call[0][0]["type"] for call in call_args_list]
    assert "ingestion_update" in types


@pytest.mark.asyncio
async def test_poll_once_updates_snapshot_on_change(poller, mock_ws_manager):
    await poller.poll_once()
    assert poller._last_snapshot != {}
    assert "system_health" in poller._last_snapshot


# ---------------------------------------------------------------------------
# _poll_system_health — returns disconnected on exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_system_health_returns_disconnected_on_exception(poller, mock_os_service):
    mock_os_service.get_cluster_health.side_effect = Exception("Connection refused")
    result = await poller._poll_system_health()
    assert result == {"system_health": {"cluster": {"status": "disconnected"}}}


@pytest.mark.asyncio
async def test_poll_system_health_returns_full_data_on_success(poller, mock_os_service):
    result = await poller._poll_system_health()
    assert "system_health" in result
    health = result["system_health"]
    assert "cluster" in health
    assert "nodes" in health
    assert "indices" in health
    assert "overview" in health
    assert "knn" in health


# ---------------------------------------------------------------------------
# _poll_ingestion — returns empty dict on exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_ingestion_graceful_on_exception(poller, mock_os_service):
    mock_os_service.get_active_ingestions.side_effect = Exception("OpenSearch down")
    result = await poller._poll_ingestion()
    # Should still return structure with empty active list
    assert result["ingestion"]["active"] == []
    assert "pipeline" in result["ingestion"]


@pytest.mark.asyncio
async def test_poll_ingestion_returns_active_and_pipeline(poller, mock_os_service):
    mock_os_service.get_active_ingestions.return_value = [{"document_id": "doc1"}]
    result = await poller._poll_ingestion()
    assert "ingestion" in result
    assert result["ingestion"]["active"] == [{"document_id": "doc1"}]
    assert "pipeline" in result["ingestion"]
    assert result["ingestion"]["pipeline"] == {"busy": True}


# ---------------------------------------------------------------------------
# _poll_logs — reads new lines from log file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_logs_reads_new_json_lines(poller, tmp_path):
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    log_file = tmp_path / f"rag-{today}.log"
    entry1 = {"level": "INFO", "message": "Started ingestion"}
    entry2 = {"level": "ERROR", "message": "Failed to parse"}
    log_file.write_text(json.dumps(entry1) + "\n" + json.dumps(entry2) + "\n")

    entries = await poller._poll_logs()
    assert len(entries) == 2
    assert entries[0]["message"] == "Started ingestion"
    assert entries[1]["level"] == "ERROR"


@pytest.mark.asyncio
async def test_poll_logs_returns_empty_when_no_log_file(poller):
    # log_dir has no log file for today
    entries = await poller._poll_logs()
    assert entries == []


@pytest.mark.asyncio
async def test_poll_logs_only_returns_new_lines(poller, tmp_path):
    """Second call should only return lines added after the first call."""
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    log_file = tmp_path / f"rag-{today}.log"
    entry1 = {"level": "INFO", "message": "First line"}
    log_file.write_text(json.dumps(entry1) + "\n")

    # First read
    entries = await poller._poll_logs()
    assert len(entries) == 1

    # Append a new line
    entry2 = {"level": "INFO", "message": "Second line"}
    with open(log_file, "a") as f:
        f.write(json.dumps(entry2) + "\n")

    # Second read — should only return the new entry
    entries = await poller._poll_logs()
    assert len(entries) == 1
    assert entries[0]["message"] == "Second line"


@pytest.mark.asyncio
async def test_poll_logs_handles_non_json_lines(poller, tmp_path):
    """Non-JSON lines should be wrapped in {'raw': ...}."""
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    log_file = tmp_path / f"rag-{today}.log"
    log_file.write_text("plain text log line\n")

    entries = await poller._poll_logs()
    assert len(entries) == 1
    assert entries[0] == {"raw": "plain text log line"}


@pytest.mark.asyncio
async def test_poll_logs_returns_empty_when_no_new_content(poller, tmp_path):
    """Calling poll_logs twice without new content returns empty list second time."""
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    log_file = tmp_path / f"rag-{today}.log"
    log_file.write_text(json.dumps({"msg": "hello"}) + "\n")

    await poller._poll_logs()  # consume existing content
    entries = await poller._poll_logs()  # nothing new
    assert entries == []


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

def test_stop_sets_running_false(poller):
    poller._running = True
    poller.stop()
    assert poller._running is False
