# tests/test_ingestion.py
import hashlib
import tempfile
from pathlib import Path

import pytest


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
    pipeline._doc_statuses[doc_id]["status"] = "failed"

    result2 = await pipeline.enqueue(str(pdf))
    assert result2["status"] == "pending"
    assert result2["document_id"] != doc_id


def test_validate_file_accepts_valid_pdf():
    from src.ingestion import validate_file

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 test content")
        f.flush()
        result = validate_file(f.name, max_size_mb=100)
        assert result["valid"] is True


def test_validate_file_rejects_non_pdf():
    from src.ingestion import validate_file

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(b"not a pdf")
        f.flush()
        result = validate_file(f.name, max_size_mb=100)
        assert result["valid"] is False
        assert "PDF" in result["reason"]


def test_validate_file_rejects_oversized():
    from src.ingestion import validate_file

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF" + b"x" * (2 * 1024 * 1024))  # ~2MB
        f.flush()
        result = validate_file(f.name, max_size_mb=1)  # 1MB limit
        assert result["valid"] is False
        assert "size" in result["reason"].lower()


def test_compute_file_hash():
    from src.ingestion import compute_file_hash

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content for hashing")
        f.flush()
        h = compute_file_hash(f.name)
        expected = hashlib.sha256(b"test content for hashing").hexdigest()
        assert h == expected


@pytest.fixture
def mock_os_client():
    """Mock OpenSearch client."""
    from unittest.mock import MagicMock
    client = MagicMock()
    client.index = MagicMock()
    client.search = MagicMock(return_value={"hits": {"hits": []}})
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
    return IngestionPipeline(config=config, rag_engine=MagicMock(), logger=MagicMock(), opensearch_client=mock_os_client)


@pytest.mark.asyncio
async def test_persist_status_success(pipeline_with_os, mock_os_client, tmp_path):
    """Status changes are persisted to OpenSearch."""
    pdf = tmp_path / "inbox" / "persist.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    result = await pipeline_with_os.enqueue(str(pdf))
    doc_id = result["document_id"]
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
    pipeline = IngestionPipeline(config=config, rag_engine=MagicMock(), logger=MagicMock(), opensearch_client=os_client)
    pdf = tmp_path / "inbox" / "fail.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
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
        "hits": {"hits": [{"_source": {
            "document_id": "doc-123", "file_name": "test.pdf",
            "file_path": "/some/path/test.pdf", "file_hash": "abc123",
            "status": "ready", "stages": [], "metadata": {}, "ingested_at": "2026-03-23T00:00:00Z",
        }}]}
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
    pipeline = IngestionPipeline(config=config, rag_engine=MagicMock(), logger=MagicMock(), opensearch_client=os_client)
    assert "doc-123" in pipeline._doc_statuses
    assert "abc123" in pipeline._known_hashes
    assert "/some/path/test.pdf" in pipeline._path_to_doc_id
