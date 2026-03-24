# Heartbeat-Ingestion Callback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the buggy batch-enqueue heartbeat flow with a callback-driven loop that ingests one file at a time and reports results immediately via OpenClaw's `/hooks/agent` endpoint.

**Architecture:** New `ingest_next` tool picks one file from inbox. MCP server processes it in background. On completion, `_notify_gateway()` POSTs to `/hooks/agent`, triggering a Katrina turn that reports results and starts the next file. Heartbeat is silent during active ingestion.

**Tech Stack:** Python 3.12, FastMCP 3.x, aiohttp, OpenClaw gateway hooks

**Spec:** `docs/superpowers/specs/2026-03-23-heartbeat-ingestion-callback-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/config.py` | Add `CallbackConfig` dataclass with gateway_port, hooks_token, notify_to |
| `src/ingestion.py` | Add `_notify_gateway()`, call it at end of `_process_single` |
| `src/server.py` | New `ingest_next` tool, add busy-guard to `ingest_inbox`, enhance `get_doc_status` |
| `.env.example` | Add 3 new env vars |
| `~/.openclaw/extensions/insurance-rag/index.ts` | Add `ingest_next` tool definition |
| `~/.openclaw/workspace/HEARTBEAT.md` | Rewrite with heartbeat + callback modes |
| `tests/test_ingestion.py` | Tests for callback and notify |
| `tests/test_server.py` | Tests for `ingest_next` tool |

---

### Task 1: Add CallbackConfig to config.py

**Files:**
- Modify: `src/config.py`
- Modify: `.env.example`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_config_has_callback_fields(monkeypatch):
    """Config loads callback fields from env vars."""
    from src.config import load_config
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test")
    monkeypatch.setenv("VISION_API_KEY", "test")
    monkeypatch.setenv("OPENCLAW_HOOKS_TOKEN", "test-token")
    monkeypatch.setenv("OPENCLAW_GATEWAY_PORT", "18789")
    monkeypatch.setenv("OPENCLAW_NOTIFY_TO", "+1234567890")
    with monkeypatch.context() as m:
        m.setattr("src.config.load_dotenv", lambda: None)
        config = load_config()
    assert config.callback.hooks_token == "test-token"
    assert config.callback.gateway_port == 18789
    assert config.callback.notify_to == "+1234567890"


def test_config_callback_defaults(monkeypatch):
    """Callback fields have sensible defaults (all optional)."""
    from src.config import load_config
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test")
    monkeypatch.setenv("VISION_API_KEY", "test")
    with monkeypatch.context() as m:
        m.setattr("src.config.load_dotenv", lambda: None)
        config = load_config()
    assert config.callback.hooks_token == ""
    assert config.callback.gateway_port == 18789
    assert config.callback.notify_to == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && PYTHONPATH=. .venv/bin/python -m pytest tests/test_config.py::test_config_has_callback_fields tests/test_config.py::test_config_callback_defaults -v`
Expected: FAIL with `AttributeError: 'AppConfig' object has no attribute 'callback'`

- [ ] **Step 3: Implement CallbackConfig**

In `src/config.py`, add after `LimitsConfig`:

```python
@dataclass
class CallbackConfig:
    hooks_token: str
    gateway_port: int
    notify_to: str
```

Add `callback: CallbackConfig` to `AppConfig`:

```python
@dataclass
class AppConfig:
    llm: ModelConfig
    embedding: ModelConfig
    vision: ModelConfig
    opensearch: OpenSearchConfig
    mineru: MinerUConfig
    paths: PathsConfig
    limits: LimitsConfig
    callback: CallbackConfig
```

In `load_config()`, add after limits:

```python
        callback=CallbackConfig(
            hooks_token=os.getenv("OPENCLAW_HOOKS_TOKEN", ""),
            gateway_port=int(os.getenv("OPENCLAW_GATEWAY_PORT", "18789")),
            notify_to=os.getenv("OPENCLAW_NOTIFY_TO", ""),
        ),
```

- [ ] **Step 4: Update .env.example**

Append to `.env.example`:

```
# OpenClaw Gateway Callback (optional — enables instant ingestion notifications)
OPENCLAW_HOOKS_TOKEN=
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_NOTIFY_TO=
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && PYTHONPATH=. .venv/bin/python -m pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add src/config.py .env.example tests/test_config.py
git commit -m "feat: add CallbackConfig for gateway hooks"
```

---

### Task 2: Add `_notify_gateway` to IngestionPipeline

**Files:**
- Modify: `src/ingestion.py`
- Modify: `tests/test_ingestion.py`

- [ ] **Step 0: Fix existing test fixtures for new callback config**

All existing `MagicMock()` configs in `tests/test_ingestion.py` must explicitly set callback attributes. Otherwise `MagicMock` auto-creates truthy values and `_callback_enabled` will be `True` in all existing tests.

Update the `pipeline` fixture (line ~11):
```python
@pytest.fixture
def pipeline(tmp_path):
    """Create a minimal IngestionPipeline with mocked dependencies."""
    from unittest.mock import MagicMock
    from src.ingestion import IngestionPipeline

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    config.callback.hooks_token = ""
    config.callback.gateway_port = 18789
    config.callback.notify_to = ""
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir()

    rag = MagicMock()
    logger = MagicMock()
    logger.log = MagicMock()

    return IngestionPipeline(config=config, rag_engine=rag, logger=logger)
```

Update the `pipeline_with_os` fixture (line ~116) — add these 3 lines after the paths:
```python
    config.callback.hooks_token = ""
    config.callback.gateway_port = 18789
    config.callback.notify_to = ""
```

Update ALL other inline `MagicMock()` config creations in the file (in `test_persist_status_failure_increments_counter`, `test_load_persisted_state`, `test_recover_crashed_file_exists`, `test_recover_crashed_file_gone`) — add the same 3 lines to each.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ingestion.py`:

```python
@pytest.mark.asyncio
async def test_notify_gateway_called_on_ready(tmp_path):
    """Gateway callback fires when document reaches 'ready' state."""
    from unittest.mock import MagicMock, AsyncMock, patch
    from src.ingestion import IngestionPipeline

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    config.callback.hooks_token = "test-token"
    config.callback.gateway_port = 18789
    config.callback.notify_to = "+1234567890"
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir()

    pipeline = IngestionPipeline(
        config=config, rag_engine=MagicMock(), logger=MagicMock()
    )
    assert pipeline._callback_enabled is True

    # Simulate a completed doc status
    pipeline._doc_statuses["doc-1"] = {
        "document_id": "doc-1",
        "file_name": "test.pdf",
        "status": "ready",
    }

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_post = AsyncMock(return_value=mock_resp)
        mock_session = AsyncMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        await pipeline._notify_gateway("doc-1", pipeline._doc_statuses["doc-1"])

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "hooks/agent" in str(call_kwargs)


@pytest.mark.asyncio
async def test_notify_gateway_disabled_without_token(tmp_path):
    """No callback when hooks_token is empty."""
    from unittest.mock import MagicMock, patch
    from src.ingestion import IngestionPipeline

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    config.callback.hooks_token = ""
    config.callback.gateway_port = 18789
    config.callback.notify_to = ""
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir()

    pipeline = IngestionPipeline(
        config=config, rag_engine=MagicMock(), logger=MagicMock()
    )
    assert pipeline._callback_enabled is False

    with patch("aiohttp.ClientSession") as mock_session_cls:
        await pipeline._notify_gateway("doc-1", {"file_name": "x.pdf", "status": "ready"})
        mock_session_cls.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && PYTHONPATH=. .venv/bin/python -m pytest tests/test_ingestion.py::test_notify_gateway_called_on_ready tests/test_ingestion.py::test_notify_gateway_disabled_without_token -v`
Expected: FAIL — `_callback_enabled` and `_notify_gateway` don't exist yet

- [ ] **Step 3: Install aiohttp and update CLAUDE.md**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/uv pip install aiohttp`

Also update `CLAUDE.md` — in the `## Setup 步驟` section, add `aiohttp` to the `uv pip install` line:
```
uv pip install "raganything>=1.2.9" "mineru[mlx]>=2.7.6" fastmcp watchdog opensearch-py python-dotenv pytest pytest-asyncio aiohttp
```

- [ ] **Step 4: Implement `_notify_gateway` and callback config in IngestionPipeline**

In `src/ingestion.py`, modify `__init__` to accept and store callback config:

```python
class IngestionPipeline:
    def __init__(self, config: AppConfig, rag_engine: RAGEngine, logger: RAGLogger,
                 opensearch_client=None):
        self._config = config
        self._rag = rag_engine
        self._logger = logger
        self._os_client = opensearch_client
        self._queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._doc_statuses: dict[str, dict] = {}
        self._known_hashes: set[str] = set()
        self._path_to_doc_id: dict[str, str] = {}
        self._persist_failures: int = 0

        # Gateway callback config
        self._gateway_port = config.callback.gateway_port
        self._hooks_token = config.callback.hooks_token
        self._notify_to = config.callback.notify_to
        try:
            import aiohttp  # noqa: F401
            self._callback_enabled = bool(self._hooks_token)
        except ImportError:
            self._callback_enabled = False
            _logger_mod.warning("aiohttp not installed, gateway callbacks disabled")

        if self._os_client:
            self._load_persisted_state()
```

Add the `_notify_gateway` method:

```python
    async def _notify_gateway(self, doc_id: str, status: dict):
        """Notify OpenClaw gateway that ingestion completed."""
        if not self._callback_enabled:
            return

        import aiohttp
        url = f"http://127.0.0.1:{self._gateway_port}/hooks/agent"
        payload = {
            "message": (
                f"[入庫回調] {status['file_name']} 完成，狀態：{status['status']}，"
                f"document_id: {doc_id}。按 HEARTBEAT.md 嘅「回調處理」流程執行。"
            ),
            "deliver": True,
            "channel": "whatsapp",
            "to": self._notify_to,
        }
        headers = {"Authorization": f"Bearer {self._hooks_token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        _logger_mod.warning("Gateway callback failed: HTTP %d", resp.status)
        except Exception as e:
            _logger_mod.warning("Gateway callback error: %s", e)
```

- [ ] **Step 5: Add `_notify_gateway` calls to `_process_single`**

At the end of `_process_single`, after every terminal state (`ready`, `failed`, `partial`, `awaiting_confirmation`), add:

```python
        await self._notify_gateway(doc_id, status)
```

There are 4 places in `_process_single` where processing terminates:
1. After validation failure (line ~184, status = "failed")
2. After hash duplicate (line ~200, status = "failed")
3. After parsing failure (line ~224, status = "failed")
4. After metadata extraction failure (line ~248, status = "partial")
5. After version check awaiting confirmation (line ~264, status = "awaiting_confirmation")
6. After successful completion (line ~274, status = "ready")

Add `await self._notify_gateway(doc_id, status)` before each `return` in cases 1-5, and at the very end for case 6.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && PYTHONPATH=. .venv/bin/python -m pytest tests/test_ingestion.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add src/ingestion.py tests/test_ingestion.py
git commit -m "feat: add gateway callback notification on ingestion completion"
```

---

### Task 3: Add `ingest_next` tool and enhance `get_doc_status`

**Files:**
- Modify: `src/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test for `ingest_next` tool registration**

Add to `tests/test_server.py`:

```python
def test_server_has_ingest_next_tool():
    """Verify ingest_next tool is registered."""
    import src.server
    importlib.reload(src.server)
    mcp = src.server.mcp

    if inspect.iscoroutinefunction(mcp.list_tools):
        tools = asyncio.run(mcp.list_tools())
    else:
        tools = mcp.list_tools()

    tool_names = [t.name if hasattr(t, "name") else str(t) for t in tools]
    assert "ingest_next" in tool_names, f"Missing tool: ingest_next. Found: {tool_names}"
```

Update existing `test_server_has_all_tools` to expect 9 tools (add `"ingest_next"` to `expected` list).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && PYTHONPATH=. .venv/bin/python -m pytest tests/test_server.py::test_server_has_ingest_next_tool -v`
Expected: FAIL — `ingest_next` not in tool list

- [ ] **Step 3: Implement `ingest_next` tool in `src/server.py`**

Add after `ingest_inbox`:

```python
@mcp.tool
async def ingest_next() -> dict[str, Any]:
    """Pick the next unprocessed PDF from inbox and start ingestion.
    Returns file name, document ID, and remaining count.
    Use this for sequential one-at-a-time ingestion (heartbeat flow)."""
    if not _pipeline or not _config:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    inbox = Path(_config.paths.inbox_dir)
    all_inbox = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"]
    all_statuses = _pipeline.get_all_statuses()
    tracked = set(
        s["file_path"] for s in all_statuses.values()
        if s["status"] not in ("failed",)
    )

    pending = [f for f in all_inbox if str(f.resolve()) not in tracked]
    if not pending:
        return {"status": "empty", "remaining": 0}

    target = pending[0]
    result = await _pipeline.enqueue(str(target))
    if not result.get("duplicate"):
        asyncio.create_task(_pipeline.process_queue())

    return {
        "status": "started",
        "file_name": target.name,
        "document_id": result["document_id"],
        "remaining": len(pending) - 1,
    }
```

- [ ] **Step 4: Add busy-guard to `ingest_inbox`**

Modify `ingest_inbox` to reject calls when ingestion is in progress:

```python
@mcp.tool
async def ingest_inbox() -> dict[str, Any]:
    """Process all PDF files in the inbox directory."""
    if not _pipeline or not _config:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    # Check if ingestion is already in progress
    processing_states = ("pending", "validating", "parsing", "extracting_metadata", "checking_version")
    all_statuses = _pipeline.get_all_statuses()
    in_progress = [s for s in all_statuses.values() if s["status"] in processing_states]
    if in_progress:
        return _error_response(
            "INGESTION_IN_PROGRESS",
            f"{len(in_progress)} file(s) already being processed. Wait for completion or use ingest_next.",
        )

    inbox = Path(_config.paths.inbox_dir)
    files = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"]

    queued = []
    skipped = []
    for f in files:
        result = await _pipeline.enqueue(str(f))
        if result.get("duplicate"):
            skipped.append(f.name)
        else:
            queued.append(f.name)

    if queued:
        asyncio.create_task(_pipeline.process_queue())

    return {"queued": len(queued), "skipped": len(skipped), "files": queued}
```

- [ ] **Step 5: Enhance `get_doc_status` response**

Modify the document dict in `get_doc_status` to include ingestion statistics:

```python
@mcp.tool
async def get_doc_status(
    document_id: str | None = None,
    file_name: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Query document processing status."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    all_statuses = _pipeline.get_all_statuses()
    docs = list(all_statuses.values())

    if document_id:
        docs = [d for d in docs if d["document_id"] == document_id]
    if file_name:
        docs = [d for d in docs if d["file_name"] == file_name]
    if status_filter:
        docs = [d for d in docs if d["status"] == status_filter]

    total = len(docs)
    docs = docs[offset : offset + limit]

    # Enrich with ingestion statistics
    enriched = []
    for d in docs:
        entry = dict(d)
        stages = d.get("stages", [])
        if stages:
            entry["processing_time_ms"] = sum(s.get("duration_ms", 0) for s in stages)
            entry["stages_summary"] = [
                {"stage": s["stage"], "status": s["status"], "duration_ms": s.get("duration_ms", 0)}
                for s in stages
            ]
        meta = d.get("metadata") or {}
        entry["company"] = meta.get("company", "")
        entry["product_name"] = meta.get("product_name", "")
        entry["product_type"] = meta.get("product_type", "")
        enriched.append(entry)

    return {"documents": enriched, "total": total, "limit": limit, "offset": offset}
```

- [ ] **Step 6: Write behavioral tests**

Add to `tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_ingest_next_returns_empty_when_no_files():
    """ingest_next returns empty status when inbox has no PDFs."""
    import src.server as srv
    from unittest.mock import MagicMock, AsyncMock
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        srv._config = MagicMock()
        srv._config.paths.inbox_dir = tmpdir
        srv._pipeline = MagicMock()
        srv._pipeline.get_all_statuses.return_value = {}

        result = await srv.ingest_next()
        assert result["status"] == "empty"
        assert result["remaining"] == 0


@pytest.mark.asyncio
async def test_ingest_next_picks_untracked_file():
    """ingest_next picks first untracked PDF and returns its name."""
    import src.server as srv
    from unittest.mock import MagicMock, AsyncMock
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf = Path(tmpdir) / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")

        srv._config = MagicMock()
        srv._config.paths.inbox_dir = tmpdir
        srv._pipeline = MagicMock()
        srv._pipeline.get_all_statuses.return_value = {}
        srv._pipeline.enqueue = AsyncMock(return_value={"document_id": "doc-1", "status": "pending"})
        srv._pipeline.process_queue = AsyncMock()

        result = await srv.ingest_next()
        assert result["status"] == "started"
        assert result["file_name"] == "test.pdf"
        assert result["remaining"] == 0
        srv._pipeline.enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_inbox_busy_guard():
    """ingest_inbox rejects when files are already processing."""
    import src.server as srv
    from unittest.mock import MagicMock

    srv._config = MagicMock()
    srv._pipeline = MagicMock()
    srv._pipeline.get_all_statuses.return_value = {
        "doc-1": {"status": "parsing", "file_path": "/some/file.pdf"},
    }

    result = await srv.ingest_inbox()
    assert result.get("error") is True
    assert result["error_code"] == "INGESTION_IN_PROGRESS"
```

- [ ] **Step 7: Run all tests**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && PYTHONPATH=. .venv/bin/python -m pytest tests/test_server.py tests/test_ingestion.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add src/server.py tests/test_server.py
git commit -m "feat: add ingest_next tool, busy-guard on ingest_inbox, enhance get_doc_status"
```

---

### Task 4: Verify `/hooks/agent` endpoint and enable OpenClaw hooks config

**Files:**
- Modify: `~/.openclaw/openclaw.json`

This task is a **manual verification gate**. The callback design depends on the `/hooks/agent` endpoint working as expected.

- [ ] **Step 1: Generate a hooks token**

Run: `openssl rand -hex 24`

Save the output — this will be the `hooks.token`.

- [ ] **Step 2: Update `~/.openclaw/openclaw.json`**

Replace the `hooks` section:

```json
"hooks": {
    "enabled": true,
    "token": "<paste-generated-token>",
    "path": "/hooks",
    "internal": {
        "enabled": true,
        "entries": {}
    }
}
```

- [ ] **Step 3: Restart OpenClaw gateway**

Run: `openclaw gateway restart` (or however the user restarts it)

- [ ] **Step 4: Test the endpoint with curl**

```bash
curl -X POST http://127.0.0.1:18789/hooks/agent \
  -H "Authorization: Bearer <paste-generated-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test callback from MCP server", "deliver": true, "channel": "whatsapp", "to": "+17807093869"}'
```

Expected: HTTP 200, and Katrina should respond to "Test callback from MCP server" via WhatsApp.

- [ ] **Step 5: Update `.env` with the token**

Add to the project's `.env` file:

```
OPENCLAW_HOOKS_TOKEN=<same-token-as-above>
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_NOTIFY_TO=+17807093869
```

- [ ] **Step 6: Document result**

If the curl test works → proceed to Task 5.
If the curl test fails → check error (404 = hooks not enabled, 401 = wrong token, connection refused = gateway not running). The system still works in heartbeat-only mode without callbacks.

---

### Task 5: Add `ingest_next` to OpenClaw plugin

**Files:**
- Modify: `~/.openclaw/extensions/insurance-rag/index.ts`

- [ ] **Step 1: Add tool definition**

Add to the `DEFAULT_TOOLS` array in `index.ts`, after `ingest_inbox`:

```typescript
  {
    name: "ingest_next",
    description:
      "Pick the next unprocessed PDF from inbox and start ingestion. Returns file name, document ID, and remaining count. Use for one-at-a-time ingestion.",
    inputSchema: { type: "object", properties: {} },
  },
```

- [ ] **Step 2: Verify tool count**

The `DEFAULT_TOOLS` array should now have 9 entries. Count them.

- [ ] **Step 3: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
cp ~/.openclaw/extensions/insurance-rag/index.ts openclaw/plugin/insurance-rag/index.ts 2>/dev/null || true
git add openclaw/plugin/insurance-rag/index.ts
git commit -m "feat: add ingest_next tool to OpenClaw plugin"
```

---

### Task 6: Rewrite HEARTBEAT.md

**Files:**
- Modify: `~/.openclaw/workspace/HEARTBEAT.md`

- [ ] **Step 1: Write the new HEARTBEAT.md**

```markdown
# HEARTBEAT.md - Katrina 定期任務

你必須按以下步驟執行，唔好跳過。

## 定期 Heartbeat（每 5 分鐘）

### Step 1: 檢查系統狀態
Call `get_system_status` tool。睇 response 入面嘅 `inbox`：

**情況 A — 有新文件 + 冇正在處理：** `pending_files > 0` AND `processing_files = 0`
→ Call `ingest_next` tool
→ 通知用戶：「開始入庫 [file_name]，inbox 仲有 [remaining] 份」
→ 之後 reply HEARTBEAT_OK（等待回調通知）

**情況 B — 正在處理中：** `processing_files > 0`
→ reply HEARTBEAT_OK（靜音，等回調）

**情況 C — 乜都冇：** `pending_files = 0` AND `processing_files = 0`
→ 繼續 Step 2

### Step 2: 檢查完成狀態
Call `get_doc_status` tool（唔使傳任何參數）。睇有冇新嘅狀態變化：
- **ready** → 通知：「✅ [file_name] 入庫成功。公司：[company] 產品：[product_name] 耗時：[time]」
- **failed** → 警告：「❌ [file_name] 入庫失敗：[error]」
- **awaiting_confirmation** → 提醒用戶確認版本更新

### Step 3: 決定回覆
- 如果 Step 2 有新嘢 → 發送通知
- 如果乜都冇 → reply HEARTBEAT_OK

---

## 回調處理（收到 [入庫回調] 訊息時）

當你收到以 `[入庫回調]` 開頭嘅訊息：

### Step 1: 查詢入庫結果
從訊息提取 `document_id`，然後 call `get_doc_status(document_id=xxx)`

### Step 2: 通知用戶
- 成功：「✅ [file_name] 入庫成功。公司：[company] 產品：[product_name] 耗時：[processing_time]」
- 失敗：「❌ [file_name] 入庫失敗：[error]」
- 等待確認：「[file_name] 需要確認版本更新」

### Step 3: 檢查下一份
Call `get_system_status` tool，睇 `inbox.pending_files`：
- 如果 `pending_files > 0`：Call `ingest_next`，通知：「開始入庫 [file_name]，仲有 [remaining] 份」
- 如果 `pending_files = 0`：通知「所有文件入庫完成」
```

- [ ] **Step 2: Sync to repo**

```bash
cp ~/.openclaw/workspace/HEARTBEAT.md /Users/weiexperimental/Desktop/GEO-Insurance-RAG/openclaw/katrina/HEARTBEAT.md 2>/dev/null || true
```

- [ ] **Step 3: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add openclaw/katrina/HEARTBEAT.md 2>/dev/null || true
git commit -m "feat: rewrite HEARTBEAT.md with callback-driven ingestion flow"
```

---

### Task 7: End-to-end verification

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && PYTHONPATH=. .venv/bin/python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Restart OpenClaw gateway**

Restart gateway so it picks up new plugin tools and HEARTBEAT.md.

- [ ] **Step 3: Verify Katrina sees `ingest_next` tool**

Send a WhatsApp message to Katrina: "你有邊啲 tools？"
Expected: She lists 9 tools including `ingest_next`.

- [ ] **Step 4: Test heartbeat flow**

Wait for next heartbeat. If there are files in inbox:
- Katrina should call `get_system_status`
- See `pending_files > 0`
- Call `ingest_next` (NOT `ingest_inbox`)
- Report: "開始入庫 [filename]，inbox 仲有 [N] 份"

- [ ] **Step 5: Test callback flow**

After file completes:
- MCP server should POST to `/hooks/agent`
- Katrina should receive `[入庫回調]` message
- Katrina should report results
- Katrina should call `ingest_next` for next file (if any)

- [ ] **Step 6: Verify no spurious messages**

During ingestion, heartbeat should return HEARTBEAT_OK (silent).
No "已開始入庫 0 份文件" messages.
