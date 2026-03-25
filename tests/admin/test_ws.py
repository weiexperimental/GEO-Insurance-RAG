"""Tests for admin/backend/ws.py — ConnectionManager."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from admin.backend.ws import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.fixture
def mock_ws():
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_adds_to_active(manager, mock_ws):
    await manager.connect(mock_ws)
    assert mock_ws in manager.active
    mock_ws.accept.assert_awaited_once()


# ---------------------------------------------------------------------------
# disconnect
# ---------------------------------------------------------------------------

def test_disconnect_removes_from_active(manager, mock_ws):
    manager.active.append(mock_ws)
    manager.disconnect(mock_ws)
    assert mock_ws not in manager.active


def test_disconnect_noop_when_not_present(manager, mock_ws):
    # Should not raise when ws is not in active list
    manager.disconnect(mock_ws)
    assert manager.active == []


# ---------------------------------------------------------------------------
# broadcast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_sends_to_all_active(manager):
    ws1, ws2 = MagicMock(), MagicMock()
    ws1.send_json = AsyncMock()
    ws2.send_json = AsyncMock()
    manager.active = [ws1, ws2]

    msg = {"type": "update", "data": {"count": 1}}
    await manager.broadcast(msg)

    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections(manager):
    ws_good = MagicMock()
    ws_good.send_json = AsyncMock()

    ws_dead = MagicMock()
    ws_dead.send_json = AsyncMock(side_effect=RuntimeError("connection closed"))

    manager.active = [ws_good, ws_dead]

    await manager.broadcast({"type": "ping"})

    assert ws_good in manager.active
    assert ws_dead not in manager.active
    ws_good.send_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_empty_active_list(manager):
    # Should not raise when no connections are active
    await manager.broadcast({"type": "ping"})


# ---------------------------------------------------------------------------
# send_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_snapshot_sends_when_snapshot_set(manager, mock_ws):
    manager._snapshot = {"ingestion": {"status": "idle"}}
    await manager.send_snapshot(mock_ws)

    mock_ws.send_json.assert_awaited_once()
    call_arg = mock_ws.send_json.call_args[0][0]
    assert call_arg["type"] == "snapshot"
    assert call_arg["data"] == {"ingestion": {"status": "idle"}}
    assert "timestamp" in call_arg


@pytest.mark.asyncio
async def test_send_snapshot_skips_when_empty(manager, mock_ws):
    # _snapshot is empty by default — nothing should be sent
    await manager.send_snapshot(mock_ws)
    mock_ws.send_json.assert_not_awaited()


# ---------------------------------------------------------------------------
# update_snapshot
# ---------------------------------------------------------------------------

def test_update_snapshot_merges_data(manager):
    manager.update_snapshot({"key1": "value1"})
    manager.update_snapshot({"key2": "value2"})
    assert manager._snapshot == {"key1": "value1", "key2": "value2"}


def test_update_snapshot_overwrites_existing_key(manager):
    manager._snapshot = {"status": "idle"}
    manager.update_snapshot({"status": "running"})
    assert manager._snapshot["status"] == "running"
