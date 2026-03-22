# tests/test_ingestion.py
import hashlib
import tempfile
from pathlib import Path

import pytest


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
