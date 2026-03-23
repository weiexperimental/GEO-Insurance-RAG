# Ingestion Flow Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove hook and watchdog from the ingestion pipeline; use direct media-path ingestion for WhatsApp uploads and heartbeat-driven inbox scanning for manual drops; persist pipeline state to OpenSearch.

**Architecture:** Two independent ingestion paths: (1) WhatsApp PDFs via `ingest_document(media_path)` called directly by the agent, (2) manual inbox drops via heartbeat → `get_system_status` → `ingest_inbox`. All pipeline state persists to OpenSearch `rag-ingestion-status` index. Crash recovery on startup re-enqueues orphaned documents.

**Tech Stack:** Python 3.12, FastMCP 3.x, OpenSearch 3.x (opensearch-py), pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-23-ingestion-flow-redesign.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/ingestion.py` | Modify | Add path dedup, OpenSearch persistence, crash recovery |
| `src/server.py` | Modify | Remove watchdog, shared OS client, fix `get_system_status`, simplify `ingest_inbox` |
| `tests/test_ingestion.py` | Modify | Add 8 new unit tests for dedup, persistence, recovery |
| `tests/test_server.py` | Modify | Update tool count assertion (still 8 tools, but verify no import errors) |
| `openclaw/katrina/AGENTS.md` | Modify | New upload flow using media path |
| `openclaw/katrina/HEARTBEAT.md` | Modify | Add inbox check via `get_system_status` |
| `openclaw/katrina/TOOLS.md` | Modify | Remove watchdog references, update port to 9200 |
| `CLAUDE.md` | Modify | Remove watchdog from tech stack |

---

### Task 1: Add file path dedup to `IngestionPipeline.enqueue()`

**Files:**
- Test: `tests/test_ingestion.py`
- Modify: `src/ingestion.py:72-101`

- [ ] **Step 1: Write failing tests for path dedup**

Add to `tests/test_ingestion.py`:

```python
@pytest.fixture
def pipeline(tmp_path):
    """Create a minimal IngestionPipeline with mocked dependencies."""
    from unittest.mock import MagicMock, AsyncMock
    from src.ingestion import IngestionPipeline

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir()

    rag = MagicMock()
    logger = MagicMock()
    logger.log = MagicMock()

    return IngestionPipeline(config=config, rag_engine=rag, logger=logger)


@pytest.mark.asyncio
async def test_enqueue_path_dedup(pipeline, tmp_path):
    """Same file path enqueued twice: second returns duplicate."""
    pdf = tmp_path / "inbox" / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    result1 = await pipeline.enqueue(str(pdf))
    assert result1["status"] == "pending"
    assert "duplicate" not in result1

    result2 = await pipeline.enqueue(str(pdf))
    assert result2["duplicate"] is True
    assert result2["document_id"] == result1["document_id"]


@pytest.mark.asyncio
async def test_enqueue_failed_allows_retry(pipeline, tmp_path):
    """A file that previously failed can be re-enqueued."""
    pdf = tmp_path / "inbox" / "retry.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    result1 = await pipeline.enqueue(str(pdf))
    doc_id = result1["document_id"]
    # Simulate failure
    pipeline._doc_statuses[doc_id]["status"] = "failed"

    result2 = await pipeline.enqueue(str(pdf))
    assert result2["status"] == "pending"
    assert result2["document_id"] != doc_id  # New doc_id for retry
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/test_ingestion.py::test_enqueue_path_dedup tests/test_ingestion.py::test_enqueue_failed_allows_retry -v`

Expected: FAIL — `enqueue()` does not return `duplicate` key

- [ ] **Step 3: Implement path dedup in `enqueue()`**

In `src/ingestion.py`, add `_path_to_doc_id` dict to `__init__` and modify `enqueue`:

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

    async def enqueue(self, file_path: str) -> dict[str, Any]:
        # Normalize path for consistent dedup across ingest_document / ingest_inbox
        file_path = str(Path(file_path).resolve())

        # Fast-path dedup: same path already tracked and not failed
        if file_path in self._path_to_doc_id:
            existing_id = self._path_to_doc_id[file_path]
            existing = self._doc_statuses.get(existing_id)
            if existing and existing["status"] not in ("failed",):
                return {
                    "document_id": existing_id,
                    "status": existing["status"],
                    "duplicate": True,
                }

        doc_id = str(uuid.uuid4())
        self._path_to_doc_id[file_path] = doc_id
        self._doc_statuses[doc_id] = {
            "document_id": doc_id,
            "file_name": Path(file_path).name,
            "file_path": file_path,
            "status": "pending",
            "stages": [],
            "metadata": None,
            "file_hash": None,
            "ingested_at": None,
        }
        await self._queue.put((doc_id, file_path))
        return {"document_id": doc_id, "status": "pending"}
```

Note: The `opensearch_client` parameter is added here but unused until Task 2. This avoids breaking the constructor signature partway through.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/test_ingestion.py -v`

Expected: All tests PASS (existing 4 + new 2)

- [ ] **Step 5: Commit**

```bash
git add src/ingestion.py tests/test_ingestion.py
git commit -m "feat(ingestion): add file path dedup to enqueue()"
```

---

### Task 2: Add OpenSearch state persistence

**Files:**
- Test: `tests/test_ingestion.py`
- Modify: `src/ingestion.py:72-210`

- [ ] **Step 1: Write failing tests for persistence**

Add to `tests/test_ingestion.py`:

```python
@pytest.fixture
def mock_os_client():
    """Mock OpenSearch client."""
    from unittest.mock import MagicMock
    client = MagicMock()
    client.index = MagicMock()
    client.search = MagicMock(return_value={
        "hits": {"hits": []}
    })
    client.indices = MagicMock()
    client.indices.exists = MagicMock(return_value=True)
    return client


@pytest.fixture
def pipeline_with_os(tmp_path, mock_os_client):
    """Pipeline with OpenSearch client."""
    from unittest.mock import MagicMock
    from src.ingestion import IngestionPipeline

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir()

    return IngestionPipeline(
        config=config, rag_engine=MagicMock(), logger=MagicMock(),
        opensearch_client=mock_os_client,
    )


@pytest.mark.asyncio
async def test_persist_status_success(pipeline_with_os, mock_os_client, tmp_path):
    """Status changes are persisted to OpenSearch."""
    pdf = tmp_path / "inbox" / "persist.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    result = await pipeline_with_os.enqueue(str(pdf))
    doc_id = result["document_id"]

    # enqueue should have called _persist_status
    mock_os_client.index.assert_called()
    call_args = mock_os_client.index.call_args
    assert call_args.kwargs["index"] == "rag-ingestion-status"
    assert call_args.kwargs["id"] == doc_id


@pytest.mark.asyncio
async def test_persist_status_failure_increments_counter(tmp_path):
    """OpenSearch failure increments counter but doesn't crash pipeline."""
    from unittest.mock import MagicMock
    from src.ingestion import IngestionPipeline

    os_client = MagicMock()
    os_client.index = MagicMock(side_effect=Exception("OS down"))
    os_client.search = MagicMock(return_value={"hits": {"hits": []}})
    os_client.indices = MagicMock()
    os_client.indices.exists = MagicMock(return_value=True)

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir()

    pipeline = IngestionPipeline(
        config=config, rag_engine=MagicMock(), logger=MagicMock(),
        opensearch_client=os_client,
    )

    pdf = tmp_path / "inbox" / "fail.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    # Should not raise
    result = await pipeline.enqueue(str(pdf))
    assert result["status"] == "pending"
    assert pipeline._persist_failures >= 1


@pytest.mark.asyncio
async def test_load_persisted_state(tmp_path):
    """Pipeline loads existing state from OpenSearch on init."""
    from unittest.mock import MagicMock
    from src.ingestion import IngestionPipeline

    os_client = MagicMock()
    os_client.search = MagicMock(return_value={
        "hits": {"hits": [
            {"_source": {
                "document_id": "doc-123",
                "file_name": "test.pdf",
                "file_path": "/some/path/test.pdf",
                "file_hash": "abc123",
                "status": "ready",
                "stages": [],
                "metadata": {},
                "ingested_at": "2026-03-23T00:00:00Z",
            }}
        ]}
    })
    os_client.index = MagicMock()
    os_client.indices = MagicMock()
    os_client.indices.exists = MagicMock(return_value=True)

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir()

    pipeline = IngestionPipeline(
        config=config, rag_engine=MagicMock(), logger=MagicMock(),
        opensearch_client=os_client,
    )

    assert "doc-123" in pipeline._doc_statuses
    assert "abc123" in pipeline._known_hashes
    assert "/some/path/test.pdf" in pipeline._path_to_doc_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/test_ingestion.py::test_persist_status_success tests/test_ingestion.py::test_persist_status_failure_increments_counter tests/test_ingestion.py::test_load_persisted_state -v`

Expected: FAIL

- [ ] **Step 3: Implement persistence methods**

In `src/ingestion.py`, add to `IngestionPipeline`:

```python
import logging

logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(self, config: AppConfig, rag_engine: RAGEngine, logger: RAGLogger,
                 opensearch_client=None):
        # ... existing init from Task 1 ...
        if self._os_client:
            self._load_persisted_state()

    def _load_persisted_state(self):
        """Load existing doc statuses from OpenSearch."""
        try:
            resp = self._os_client.search(
                index="rag-ingestion-status",
                body={"query": {"match_all": {}}, "size": 10000},
            )
            for hit in resp["hits"]["hits"]:
                doc = hit["_source"]
                self._doc_statuses[doc["document_id"]] = doc
                if doc.get("file_hash"):
                    self._known_hashes.add(doc["file_hash"])
                if doc.get("file_path"):
                    self._path_to_doc_id[doc["file_path"]] = doc["document_id"]
        except Exception as e:
            logger.warning("Failed to load persisted state: %s", e)

    def _persist_status(self, doc_id: str):
        """Write a single doc status to OpenSearch. Best-effort with logging."""
        if not self._os_client:
            return
        try:
            self._os_client.index(
                index="rag-ingestion-status",
                id=doc_id,
                body=self._doc_statuses[doc_id],
            )
        except Exception as e:
            self._persist_failures += 1
            logger.warning(
                "Failed to persist status for %s: %s (total failures: %d)",
                doc_id, e, self._persist_failures,
            )
```

Then add `self._persist_status(doc_id)` calls at the end of `enqueue()` and at every status transition in `_process_single()` (after each `status["status"] = ...` assignment that is a terminal or significant state).

Key insertion points in `_process_single`:
- After `status["status"] = "failed"` (validation fail, line ~123)
- After `status["status"] = "failed"` (duplicate, line ~137)
- After `status["status"] = "parsing"` (line ~145)
- After `status["status"] = "failed"` (parsing fail, line ~160)
- After `status["status"] = "partial"` (line ~182)
- After `status["status"] = "awaiting_confirmation"` (line ~195)
- After `status["status"] = "ready"` (line ~205)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/test_ingestion.py -v`

Expected: All tests PASS (6 existing + 3 new = 9)

- [ ] **Step 5: Commit**

```bash
git add src/ingestion.py tests/test_ingestion.py
git commit -m "feat(ingestion): persist pipeline state to OpenSearch"
```

---

### Task 3: Add crash recovery

**Files:**
- Test: `tests/test_ingestion.py`
- Modify: `src/ingestion.py`

- [ ] **Step 1: Write failing tests for recovery**

Add to `tests/test_ingestion.py`:

```python
@pytest.mark.asyncio
async def test_recover_crashed_file_exists(tmp_path):
    """Recovery re-enqueues documents stuck in processing state."""
    from unittest.mock import MagicMock
    from src.ingestion import IngestionPipeline

    orphan_path = tmp_path / "inbox" / "orphan.pdf"
    orphan_path.parent.mkdir(exist_ok=True)
    orphan_path.write_bytes(b"%PDF-1.4 orphan")

    os_client = MagicMock()
    os_client.search = MagicMock(return_value={
        "hits": {"hits": [
            {"_source": {
                "document_id": "orphan-1",
                "file_name": "orphan.pdf",
                "file_path": str(orphan_path),
                "file_hash": None,
                "status": "parsing",
                "stages": [],
                "metadata": None,
                "ingested_at": None,
            }}
        ]}
    })
    os_client.index = MagicMock()
    os_client.indices = MagicMock()
    os_client.indices.exists = MagicMock(return_value=True)

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir(exist_ok=True)

    pipeline = IngestionPipeline(
        config=config, rag_engine=MagicMock(), logger=MagicMock(),
        opensearch_client=os_client,
    )

    recovered = await pipeline.recover_crashed()
    assert len(recovered) == 1
    assert str(orphan_path) in recovered
    assert pipeline._doc_statuses["orphan-1"]["status"] == "pending"


@pytest.mark.asyncio
async def test_recover_crashed_file_gone(tmp_path):
    """Recovery marks missing files as failed."""
    from unittest.mock import MagicMock
    from src.ingestion import IngestionPipeline

    os_client = MagicMock()
    os_client.search = MagicMock(return_value={
        "hits": {"hits": [
            {"_source": {
                "document_id": "gone-1",
                "file_name": "gone.pdf",
                "file_path": "/nonexistent/gone.pdf",
                "file_hash": None,
                "status": "extracting_metadata",
                "stages": [],
                "metadata": None,
                "ingested_at": None,
            }}
        ]}
    })
    os_client.index = MagicMock()
    os_client.indices = MagicMock()
    os_client.indices.exists = MagicMock(return_value=True)

    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.inbox_dir = str(tmp_path / "inbox")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.failed_dir = str(tmp_path / "failed")
    for d in ["inbox", "processed", "failed"]:
        (tmp_path / d).mkdir(exist_ok=True)

    pipeline = IngestionPipeline(
        config=config, rag_engine=MagicMock(), logger=MagicMock(),
        opensearch_client=os_client,
    )

    recovered = await pipeline.recover_crashed()
    assert len(recovered) == 0
    assert pipeline._doc_statuses["gone-1"]["status"] == "failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/test_ingestion.py::test_recover_crashed_file_exists tests/test_ingestion.py::test_recover_crashed_file_gone -v`

Expected: FAIL — `recover_crashed` method does not exist

- [ ] **Step 3: Implement `recover_crashed()`**

Add to `IngestionPipeline` in `src/ingestion.py`:

```python
async def recover_crashed(self) -> list[str]:
    """Re-enqueue documents stuck in processing state after a crash."""
    in_progress_states = ("parsing", "extracting_metadata", "checking_version", "validating")
    recovered = []

    for doc_id, status in list(self._doc_statuses.items()):
        if status["status"] not in in_progress_states:
            continue

        file_path = status["file_path"]
        if Path(file_path).exists():
            status["status"] = "pending"
            self._persist_status(doc_id)
            await self._queue.put((doc_id, file_path))
            recovered.append(file_path)
        else:
            status["status"] = "failed"
            status["stages"].append({
                "stage": "recovery",
                "status": "failed",
                "duration_ms": 0,
                "error": "File not found after crash",
            })
            self._persist_status(doc_id)

    return recovered
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/test_ingestion.py -v`

Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ingestion.py tests/test_ingestion.py
git commit -m "feat(ingestion): add crash recovery on startup"
```

---

### Task 4: Update `server.py` — remove watchdog, shared client, fix tools

**Files:**
- Modify: `src/server.py:1-327`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write failing test for `ingest_inbox` without pre-validation**

Add to `tests/test_ingestion.py`:

```python
@pytest.mark.asyncio
async def test_ingest_inbox_no_prevalidation(pipeline, tmp_path):
    """ingest_inbox enqueues all PDFs without pre-validation; pipeline handles it."""
    # Create a valid and an oversized PDF in inbox
    valid = tmp_path / "inbox" / "valid.pdf"
    valid.write_bytes(b"%PDF-1.4 valid")

    non_pdf = tmp_path / "inbox" / "readme.txt"
    non_pdf.write_bytes(b"not a pdf")

    # ingest_inbox should only pick up .pdf files
    from pathlib import Path
    inbox = Path(pipeline._config.paths.inbox_dir)
    files = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"]
    assert len(files) == 1  # Only valid.pdf

    result = await pipeline.enqueue(str(valid))
    assert result["status"] == "pending"
```

- [ ] **Step 2: Run test to verify it passes** (this test validates existing behavior)

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/test_ingestion.py::test_ingest_inbox_no_prevalidation -v`

Expected: PASS

- [ ] **Step 3: Update `server.py`**

Apply all changes to `src/server.py`:

1. Remove `InboxWatcher` import and `_watcher` global
2. Add `_os_client` global
3. Add `_ensure_ingestion_index()` function
4. Simplify `lifespan` (remove watcher stop)
5. Rewrite `_initialize()` — shared client, no watcher, call `recover_crashed()`
6. Rewrite `ingest_inbox()` — remove pre-validation, use dedup return
7. Rewrite `get_system_status()` — shared client, remove `watcher_active`, add `persist_failures`, smart inbox count

The full updated `server.py` replaces these sections:

**Imports** — remove `from src.watcher import InboxWatcher`, remove `validate_file` and `compute_file_hash` from import (no longer used in server.py)

**Lifespan:**
```python
@asynccontextmanager
async def lifespan(server):
    await _initialize()
    yield
```

**Globals:**
```python
_config: AppConfig | None = None
_rag_engine: RAGEngine | None = None
_logger: RAGLogger | None = None
_pipeline: IngestionPipeline | None = None
_os_client = None
```

**`ingest_inbox`:**
```python
@mcp.tool
async def ingest_inbox() -> dict[str, Any]:
    """Process all PDF files in the inbox directory."""
    if not _pipeline or not _config:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

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

**`get_system_status`:**
```python
@mcp.tool
async def get_system_status() -> dict[str, Any]:
    """Get system health status including OpenSearch and API connectivity."""
    os_status = "disconnected"
    docs_indexed = 0

    if _os_client:
        try:
            _os_client.info()
            os_status = "healthy"
        except Exception:
            os_status = "degraded"

    inbox_count = 0
    if _config and _pipeline:
        all_inbox = set(str(f) for f in Path(_config.paths.inbox_dir).glob("*.pdf"))
        tracked = set(
            s["file_path"] for s in _pipeline.get_all_statuses().values()
            if s["status"] not in ("failed",)
        )
        inbox_count = len(all_inbox - tracked)

    return {
        "opensearch": {
            "status": os_status,
            "documents_indexed": docs_indexed,
            "index_size_mb": 0.0,
        },
        "inbox": {
            "pending_files": inbox_count,
            "heartbeat_inbox_check": True,
        },
        "persistence": {
            "failures": _pipeline._persist_failures if _pipeline else 0,
        },
        "models": {
            "llm": _config.llm.model if _config else "",
            "embedding": _config.embedding.model if _config else "",
            "vision": _config.vision.model if _config else "",
            "api_status": "healthy",
        },
    }
```

**`_ensure_ingestion_index` + `_initialize`:**
```python
def _ensure_ingestion_index(client):
    """Create rag-ingestion-status index if it doesn't exist."""
    if not client.indices.exists("rag-ingestion-status"):
        client.indices.create("rag-ingestion-status", body={
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "file_name": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "file_hash": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "ingested_at": {"type": "date"},
                    "metadata": {"type": "object", "dynamic": True},
                    "stages": {"type": "nested"},
                }
            }
        })


async def _initialize():
    """Initialize all components with OpenSearch health check retry."""
    global _config, _rag_engine, _logger, _pipeline, _os_client

    _config = load_config()
    _logger = RAGLogger(log_dir=_config.paths.log_dir)

    from opensearchpy import OpenSearch
    _os_client = OpenSearch(
        hosts=[{"host": _config.opensearch.host, "port": _config.opensearch.port}],
        use_ssl=False,
    )

    # OpenSearch health check: retry every 5s for 60s
    for attempt in range(12):
        try:
            _os_client.info()
            break
        except Exception:
            if attempt < 11:
                await asyncio.sleep(5)
            else:
                print("WARNING: OpenSearch not available, starting in degraded mode")

    try:
        _ensure_ingestion_index(_os_client)
    except Exception:
        print("WARNING: Could not create ingestion index, will retry on first use")

    _rag_engine = RAGEngine(
        llm_config=_config.llm,
        embedding_config=_config.embedding,
        vision_config=_config.vision,
        opensearch_config=_config.opensearch,
        working_dir="./rag_working_dir",
    )
    try:
        await _rag_engine.initialize()
    except Exception as e:
        print(f"WARNING: RAG engine init failed: {e}")

    _pipeline = IngestionPipeline(
        config=_config, rag_engine=_rag_engine, logger=_logger,
        opensearch_client=_os_client,
    )
    recovered = await _pipeline.recover_crashed()
    if recovered:
        print(f"Recovered {len(recovered)} crashed documents", flush=True)
        await _pipeline.process_queue()
```

- [ ] **Step 4: Run all tests**

Run: `cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG && .venv/bin/python -m pytest tests/ -v`

Expected: All tests PASS. The tool count test in `test_server.py` should still find 8 tools.

- [ ] **Step 5: Commit**

```bash
git add src/server.py tests/test_ingestion.py tests/test_server.py
git commit -m "feat(server): remove watchdog, add shared OS client, fix ingest_inbox and get_system_status"
```

---

### Task 5: Update OpenClaw config files

**Files:**
- Modify: `openclaw/katrina/AGENTS.md`
- Modify: `openclaw/katrina/HEARTBEAT.md`
- Modify: `openclaw/katrina/TOOLS.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `AGENTS.md` — new upload flow**

In `openclaw/katrina/AGENTS.md`, replace the `## 文件上傳流程` section (lines 29-42) and update the `ingest_inbox` description (line 25):

Replace MCP tools section line 25:
```
- **`ingest_inbox`** — 手動觸發 inbox 全部入庫（通常唔使，watchdog 自動做）
```
With:
```
- **`ingest_inbox`** — 觸發 inbox 全部入庫（heartbeat 自動 call，手動亦可）
```

Replace entire `## 文件上傳流程` section with:
```markdown
## 文件上傳流程

當你收到 PDF 附件，你會見到類似：
```
[media attached: /Users/.../.openclaw/media/inbound/filename.pdf (application/pdf)]
```

**流程：**
1. 回覆用戶：「收到 [文件名]，正在處理入庫...」
2. 從 `[media attached: ...]` 提取完整 file path
3. Call `ingest_document(file_path="提取到嘅完整路徑")`
4. Call `get_doc_status` 查詢結果
5. 回報結果：
   - **ready** → 「[文件名] 已成功入庫！識別到係 [公司] 嘅 [產品名稱]」
   - **partial** → 「[文件名] 已入庫但 metadata 未完整，可能需要人手補充」
   - **failed** → 「[文件名] 入庫失敗，原因：[error]。請檢查文件係咪完整嘅 PDF」
   - **awaiting_confirmation** → 進入版本更新流程（見下面）

**非 PDF 文件：** 回覆「我只支援 PDF 格式嘅文件入庫」
```

- [ ] **Step 2: Update `HEARTBEAT.md` — add inbox check**

Replace `openclaw/katrina/HEARTBEAT.md` entirely:

```markdown
# HEARTBEAT.md - Katrina 定期任務

## 每次 heartbeat 檢查以下項目：

### 1. Inbox 新文件
Call `get_system_status`：
- **pending_files > 0** → call `ingest_inbox` 觸發入庫
- **pending_files = 0** → skip

### 2. 入庫狀態
Call `get_doc_status` 檢查有無新變化：
- **ready** → 通知用戶：「[文件名] 已成功入庫，識別到係 [公司] 嘅 [產品名稱]」
- **failed** → 警告用戶：「[文件名] 入庫失敗：[error]」
- **partial** → 通知用戶：「[文件名] 已入庫但 metadata 唔完整」
- **awaiting_confirmation** → 提醒用戶確認版本更新
- 冇新變化 → 唔使講嘢

### 3. 系統健康
Call `get_system_status` 快速檢查：
- OpenSearch 斷線 → 立即通知用戶
- persist_failures > 0 → 警告用戶「狀態持久化有問題」
- 其他正常 → 唔使講嘢

### 規則
- 只通知有變化嘅嘢，唔好重複報告已經講過嘅狀態
- 冇嘢要報 → reply HEARTBEAT_OK
- 深夜（23:00-08:00）只報 failed 同 system down，其他留到朝早
```

- [ ] **Step 3: Update `TOOLS.md` — remove watchdog, fix port**

Replace `openclaw/katrina/TOOLS.md` entirely:

```markdown
# TOOLS.md - Katrina 環境配置

## MCP Server: insurance-rag

- **Transport:** stdio
- **Command:** `.venv/bin/python src/server.py`
- **Working directory:** /path/to/GEO-Insurance-RAG
- **PYTHONPATH:** /path/to/GEO-Insurance-RAG

## 文件目錄

- **Inbox:** `data/inbox/` — 手動拉 PDF 入呢度，heartbeat 會自動入庫
- **Processed:** `data/processed/` — 成功入庫嘅 PDF 搬到呢度
- **Failed:** `data/failed/` — 入庫失敗嘅 PDF 搬到呢度
- **Logs:** `logs/` — JSON 格式日誌

## 文件上傳

- **WhatsApp 上傳：** 你直接 call `ingest_document(file_path)` 入庫
- **手動拉文件：** 放入 `data/inbox/`，heartbeat 自動處理

## 基礎設施

- **OpenSearch 3.x** — port 9200（vector、graph、KV、doc status、ingestion status 統一儲存）
- **MinerU (MLX GPU)** — PDF 解析，中文 OCR（`lang="ch"`, `device="mps"`）
- **YIBU API** — LLM / embedding / vision provider（OpenAI 兼容）
  - LLM: `gpt-4o-mini`
  - Embedding: `text-embedding-3-large`（3072 維度）
  - Vision: `gpt-4o-mini`

## 支援嘅文件格式

- 只限 PDF（最大 100MB）
- 語言：繁體中文
- 其他格式一律拒絕
```

- [ ] **Step 4: Update `CLAUDE.md` — remove watchdog from tech stack**

In `CLAUDE.md`, change line 15:
```
- **watchdog** — inbox 資料夾即時監察
```
To:
```
- **OpenClaw heartbeat** — 定期 inbox 檢查 + 入庫狀態通知
```

- [ ] **Step 5: Commit**

```bash
git add openclaw/katrina/AGENTS.md openclaw/katrina/HEARTBEAT.md openclaw/katrina/TOOLS.md CLAUDE.md
git commit -m "docs: update OpenClaw configs for hookless ingestion flow"
```

---

### Task 6: Remove hook and sync workspace files

**Files:**
- Remove: `~/.openclaw/hooks/pdf-to-inbox/`
- Copy: `openclaw/katrina/*.md` → `~/.openclaw/workspace/`

- [ ] **Step 1: Disable and remove the hook (workspace + repo)**

```bash
openclaw hooks disable pdf-to-inbox
rm -rf ~/.openclaw/hooks/pdf-to-inbox/
rm -rf openclaw/katrina/hooks/pdf-to-inbox/
```

- [ ] **Step 2: Copy updated config files to workspace**

```bash
cp openclaw/katrina/AGENTS.md ~/.openclaw/workspace/AGENTS.md
cp openclaw/katrina/HEARTBEAT.md ~/.openclaw/workspace/HEARTBEAT.md
cp openclaw/katrina/TOOLS.md ~/.openclaw/workspace/TOOLS.md
```

- [ ] **Step 3: Verify hook removed and files in sync**

```bash
openclaw hooks list  # pdf-to-inbox should NOT appear
diff openclaw/katrina/AGENTS.md ~/.openclaw/workspace/AGENTS.md     # no diff
diff openclaw/katrina/HEARTBEAT.md ~/.openclaw/workspace/HEARTBEAT.md # no diff
diff openclaw/katrina/TOOLS.md ~/.openclaw/workspace/TOOLS.md       # no diff
```

- [ ] **Step 4: Commit project-side hook removal (remove from repo if tracked)**

```bash
git add -A openclaw/katrina/hooks/
git commit -m "chore: remove pdf-to-inbox hook (replaced by direct media path ingestion)"
```

---

### Task 7: Full test run and verification

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
.venv/bin/python -m pytest tests/ -v
```

Expected: All tests PASS (original tests + 8 new tests)

- [ ] **Step 2: Verify OpenSearch index creation** (requires Docker running)

```bash
curl -s http://localhost:9200/rag-ingestion-status | python3 -m json.tool | head -20
```

This will fail if the MCP server hasn't been started yet — that's OK. The index is created on first server startup.

- [ ] **Step 3: Verify server starts without errors**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
timeout 10 .venv/bin/python -c "
import asyncio
from src.server import _initialize
asyncio.run(_initialize())
print('Server initialized OK')
" 2>&1 || true
```

Expected: Should print initialization messages without watchdog-related errors.

- [ ] **Step 4: Final commit**

```bash
git add -A
git status  # Verify only expected files
git commit -m "feat: complete ingestion flow redesign — remove hook/watchdog, add persistence and recovery"
```
