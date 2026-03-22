# tests/test_server.py
import asyncio
import importlib
import inspect
import pytest


def test_server_has_all_tools():
    """Verify all 8 MCP tools are registered."""
    import src.server
    importlib.reload(src.server)
    mcp = src.server.mcp

    # FastMCP 3.x: list_tools() is async
    if inspect.iscoroutinefunction(mcp.list_tools):
        tools = asyncio.run(mcp.list_tools())
    else:
        tools = mcp.list_tools()

    tool_names = [t.name if hasattr(t, "name") else str(t) for t in tools]

    expected = [
        "query",
        "ingest_inbox",
        "ingest_document",
        "get_doc_status",
        "list_documents",
        "delete_document",
        "get_system_status",
        "confirm_version_update",
    ]
    for name in expected:
        assert name in tool_names, f"Missing tool: {name}. Found: {tool_names}"
