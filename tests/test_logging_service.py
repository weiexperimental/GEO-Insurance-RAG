# tests/test_logging_service.py
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_logger_writes_to_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.logging_service import RAGLogger

        logger = RAGLogger(log_dir=tmpdir, opensearch_client=None)
        logger.log(
            document="test.pdf",
            stage="parsing",
            status="success",
            duration_ms=1234,
            details={"pages": 5},
        )

        log_files = list(Path(tmpdir).glob("*.log"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["document"] == "test.pdf"
            assert entry["stage"] == "parsing"
            assert entry["status"] == "success"
            assert entry["duration_ms"] == 1234
            assert entry["details"]["pages"] == 5
            assert "timestamp" in entry


def test_logger_writes_to_opensearch_when_available():
    mock_client = MagicMock()
    from src.logging_service import RAGLogger

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = RAGLogger(log_dir=tmpdir, opensearch_client=mock_client)
        logger.log(document="test.pdf", stage="indexing", status="success")

        mock_client.index.assert_called_once()
        call_kwargs = mock_client.index.call_args
        assert call_kwargs.kwargs["index"] == "rag-logs"


def test_logger_continues_if_opensearch_fails():
    mock_client = MagicMock()
    mock_client.index.side_effect = Exception("connection refused")

    from src.logging_service import RAGLogger

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = RAGLogger(log_dir=tmpdir, opensearch_client=mock_client)
        # Should not raise
        logger.log(document="test.pdf", stage="parsing", status="success")

        # File log should still be written
        log_files = list(Path(tmpdir).glob("*.log"))
        assert len(log_files) == 1
