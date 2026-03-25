import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from src.ingestion import IngestionService, validate_file, _read_parsed_content, _file_doc_id


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.limits.max_file_size_mb = 100
    config.paths.processed_dir = "/tmp/processed"
    config.paths.failed_dir = "/tmp/failed"
    config.mineru.device = "mps"
    config.mineru.lang = "ch"
    config.llm = MagicMock()
    config.callback.gateway_port = 3000
    config.callback.hooks_token = ""
    config.callback.notify_to = ""
    return config


_DEFAULT_DOC_STATUS = {
    "_id": "doc-abc123",
    "status": "processed",
    "metadata": {"processing_start_time": 123},
}


@pytest.fixture
def mock_rag():
    rag = AsyncMock()
    rag.ingest_document = AsyncMock()
    rag.doc_status = AsyncMock()
    # Default: None for pre-check (not yet processed); tests that need the
    # post-ingest lookup value must set their own side_effect or return_value.
    rag.doc_status.get_by_id = AsyncMock(return_value=None)
    rag.doc_status.upsert = AsyncMock()
    return rag


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def service(mock_config, mock_rag, mock_logger):
    return IngestionService(mock_config, mock_rag, mock_logger)


def test_validate_file_valid(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test content")
    result = validate_file(str(pdf), max_size_mb=100)
    assert result["valid"] is True


def test_validate_file_not_pdf(tmp_path):
    txt = tmp_path / "test.txt"
    txt.write_text("hello")
    result = validate_file(str(txt), max_size_mb=100)
    assert result["valid"] is False
    assert "Not a PDF" in result["reason"]


def test_validate_file_too_large(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF" + b"x" * (2 * 1024 * 1024))
    result = validate_file(str(pdf), max_size_mb=1)
    assert result["valid"] is False
    assert "exceeds" in result["reason"]


@pytest.mark.asyncio
async def test_ingest_calls_rag_engine(service, mock_rag, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")

    # pre-check returns None (not processed yet), post-ingest lookup returns doc
    mock_rag.doc_status.get_by_id.side_effect = [
        None,  # pre-check
        _DEFAULT_DOC_STATUS,  # post-ingest lookup
    ]

    with patch("src.ingestion.extract_metadata", new_callable=AsyncMock, return_value={"company": "AIA"}):
        with patch("src.ingestion._read_parsed_content", return_value="test content"):
            with patch("src.ingestion.shutil"):
                result = await service.ingest(str(pdf))

    mock_rag.ingest_document.assert_awaited_once()
    assert result["status"] == "processed"


@pytest.mark.asyncio
async def test_ingest_enriches_metadata(service, mock_rag, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")

    # pre-check returns None (not processed yet), post-ingest lookup returns doc
    mock_rag.doc_status.get_by_id.side_effect = [
        None,  # pre-check
        _DEFAULT_DOC_STATUS,  # post-ingest lookup
    ]

    with patch("src.ingestion.extract_metadata", new_callable=AsyncMock, return_value={"company": "AIA"}):
        with patch("src.ingestion._read_parsed_content", return_value="content"):
            with patch("src.ingestion.shutil"):
                await service.ingest(str(pdf))

    mock_rag.doc_status.upsert.assert_awaited_once()
    call_args = mock_rag.doc_status.upsert.call_args[0][0]
    doc_id = list(call_args.keys())[0]
    assert call_args[doc_id]["metadata"]["company"] == "AIA"
    assert call_args[doc_id]["metadata"]["processing_start_time"] == 123  # preserved from LightRAG


@pytest.mark.asyncio
async def test_ingest_validation_failure(service, tmp_path):
    txt = tmp_path / "test.txt"
    txt.write_text("not a pdf")

    with patch("src.ingestion.shutil"):
        result = await service.ingest(str(txt))

    assert result["error"] == "validation_failed"


@pytest.mark.asyncio
async def test_ingest_rag_failure(service, mock_rag, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")
    mock_rag.ingest_document.side_effect = Exception("GPU OOM")

    with patch("src.ingestion.shutil"):
        with patch("src.ingestion.asyncio.sleep", new_callable=AsyncMock):
            result = await service.ingest(str(pdf))

    assert result["error"] == "ingestion_failed"


@pytest.mark.asyncio
async def test_ingest_metadata_failure_still_succeeds(service, mock_rag, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")

    mock_rag.doc_status.get_by_id.side_effect = [
        None,  # pre-check
        _DEFAULT_DOC_STATUS,  # post-ingest lookup
    ]

    with patch("src.ingestion.extract_metadata", new_callable=AsyncMock, side_effect=Exception("LLM error")):
        with patch("src.ingestion._read_parsed_content", return_value="content"):
            with patch("src.ingestion.shutil"):
                result = await service.ingest(str(pdf))

    assert result["status"] == "processed"
    assert result["metadata"] == {}


@pytest.mark.asyncio
async def test_ingest_sequential_lock(service, mock_rag, tmp_path):
    """Verify only one ingest runs at a time."""
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"
    pdf1.write_bytes(b"%PDF-1.0 a")
    pdf2.write_bytes(b"%PDF-1.0 b")

    # Four get_by_id calls: pre-check × 2 + post-ingest lookup × 2
    mock_rag.doc_status.get_by_id.side_effect = [
        None, None,  # pre-checks
        {"_id": "doc-a", "status": "processed", "metadata": {}},
        {"_id": "doc-b", "status": "processed", "metadata": {}},
    ]

    call_order = []

    async def slow_ingest(**kwargs):
        call_order.append("start")
        await asyncio.sleep(0.1)
        call_order.append("end")

    mock_rag.ingest_document.side_effect = slow_ingest

    with patch("src.ingestion.extract_metadata", new_callable=AsyncMock, return_value={}):
        with patch("src.ingestion._read_parsed_content", return_value=""):
            with patch("src.ingestion.shutil"):
                await asyncio.gather(
                    service.ingest(str(pdf1)),
                    service.ingest(str(pdf2)),
                )

    # Sequential: start-end-start-end, NOT start-start-end-end
    assert call_order == ["start", "end", "start", "end"]


def test_file_doc_id_deterministic(tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test content")
    id1 = _file_doc_id(str(pdf))
    id2 = _file_doc_id(str(pdf))
    assert id1 == id2
    assert id1.startswith("doc-")


def test_file_doc_id_different_content(tmp_path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"%PDF-1.0 content A")
    b.write_bytes(b"%PDF-1.0 content B")
    assert _file_doc_id(str(a)) != _file_doc_id(str(b))


@pytest.mark.asyncio
async def test_ingest_skips_already_processing(service, tmp_path):
    """Layer 1: in-memory _processing set rejects concurrent duplicate."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")
    canonical = str(pdf.resolve())

    # Simulate file already being processed
    service._processing.add(canonical)
    result = await service.ingest(str(pdf))
    assert result["status"] == "skipped"
    assert result["reason"] == "already_processing"
    service._processing.discard(canonical)


@pytest.mark.asyncio
async def test_ingest_skips_already_processed(service, mock_rag, tmp_path):
    """Layer 2: doc_status pre-check skips completed files."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")

    mock_rag.doc_status.get_by_id.return_value = {"status": "processed"}
    result = await service.ingest(str(pdf))
    assert result["status"] == "skipped"
    assert result["reason"] == "already_processed"
    # Should NOT have called ingest_document
    mock_rag.ingest_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_retries_stale_processing(service, mock_rag, tmp_path):
    """Layer 2: does NOT skip files stuck in 'processing' (stale from crash)."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")

    # First call for pre-check returns "processing" (stale)
    # Second call after ingest returns the full doc for enrichment
    mock_rag.doc_status.get_by_id.side_effect = [
        {"status": "processing"},  # pre-check: stale, allow retry
        {"_id": "doc-abc", "status": "processed", "metadata": {}},  # post-ingest lookup
    ]

    with patch("src.ingestion.extract_metadata", new_callable=AsyncMock, return_value={}):
        with patch("src.ingestion._read_parsed_content", return_value=""):
            with patch("src.ingestion.shutil"):
                result = await service.ingest(str(pdf))

    assert result["status"] == "processed"
    mock_rag.ingest_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_skips_if_file_moved(service, mock_rag, tmp_path):
    """Layer 3: file moved between pre-check and lock acquisition."""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.0 test")
    path_str = str(pdf)

    mock_rag.doc_status.get_by_id.return_value = None  # not in doc_status

    # Delete file to simulate it being moved by concurrent ingest
    pdf.unlink()

    result = await service.ingest(path_str)
    assert result["status"] == "skipped"
    assert result["reason"] == "file_moved"
