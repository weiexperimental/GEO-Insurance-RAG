# tests/test_server.py
import asyncio
import importlib
import inspect
import pytest


EXPECTED_TOOLS = {"query", "ingest", "ingest_all", "list_documents", "delete_document", "get_system_status"}


def test_server_has_all_tools():
    """Verify all 6 MCP tools are registered."""
    import src.server
    importlib.reload(src.server)
    mcp = src.server.mcp

    # FastMCP 3.x: list_tools() is async
    if inspect.iscoroutinefunction(mcp.list_tools):
        tools = asyncio.run(mcp.list_tools())
    else:
        tools = mcp.list_tools()

    tool_names = {t.name if hasattr(t, "name") else str(t) for t in tools}
    assert tool_names == EXPECTED_TOOLS, f"Expected {EXPECTED_TOOLS}, got {tool_names}"


@pytest.mark.asyncio
async def test_ingest_file_not_found():
    """ingest returns error for missing file."""
    import src.server as srv
    from unittest.mock import MagicMock

    srv._ingestion = MagicMock()
    result = await srv.ingest("/nonexistent/file.pdf")
    assert result.get("error") is True
    assert result["error_code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_ingest_all_empty_inbox():
    """ingest_all returns zero total when inbox has no PDFs."""
    import src.server as srv
    from unittest.mock import MagicMock
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        srv._config = MagicMock()
        srv._config.paths.inbox_dir = tmpdir
        srv._ingestion = MagicMock()

        result = await srv.ingest_all()
        assert result["total"] == 0
        assert result["results"] == []


@pytest.mark.asyncio
async def test_ingest_all_processes_files():
    """ingest_all processes each PDF and returns summary."""
    import src.server as srv
    from unittest.mock import MagicMock, AsyncMock
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf1 = Path(tmpdir) / "a.pdf"
        pdf2 = Path(tmpdir) / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4 test")
        pdf2.write_bytes(b"%PDF-1.4 test")

        srv._config = MagicMock()
        srv._config.paths.inbox_dir = tmpdir
        srv._ingestion = MagicMock()
        srv._ingestion.ingest = AsyncMock(return_value={"doc_id": "x", "status": "processed", "metadata": {}})

        result = await srv.ingest_all()
        assert result["total"] == 2
        assert result["started"] is True
        assert len(result["files"]) == 2
        # Background task is fire-and-forget; give it a tick to start
        await asyncio.sleep(0.1)
        assert srv._ingestion.ingest.call_count == 2


@pytest.mark.asyncio
async def test_delete_document_requires_confirm():
    """delete_document rejects without confirm=True."""
    import src.server as srv

    result = await srv.delete_document("doc-1", confirm=False)
    assert result.get("error") is True
    assert result["error_code"] == "INVALID_PARAMETERS"


@pytest.mark.asyncio
async def test_get_system_status_disconnected():
    """get_system_status returns disconnected when OpenSearch is down."""
    import src.server as srv

    srv._os_client = None
    srv._rag_engine = None
    srv._config = None

    result = await srv.get_system_status()
    assert result["opensearch"]["status"] == "disconnected"
    assert result["inbox"]["pending_files"] == 0
