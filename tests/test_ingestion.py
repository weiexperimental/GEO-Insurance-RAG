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
