# tests/test_watcher.py
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_watcher_detects_new_pdf():
    from src.watcher import InboxWatcher

    callback = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = InboxWatcher(inbox_dir=tmpdir, on_new_file=callback, stabilization_seconds=0.1)
        watcher.start()

        # Create a PDF file
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        time.sleep(0.5)  # Wait for stabilization + detection

        watcher.stop()
        callback.assert_called_once()
        assert "test.pdf" in str(callback.call_args)


def test_watcher_ignores_non_pdf():
    from src.watcher import InboxWatcher

    callback = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = InboxWatcher(inbox_dir=tmpdir, on_new_file=callback, stabilization_seconds=0.1)
        watcher.start()

        # Create a non-PDF file
        txt_path = Path(tmpdir) / "test.txt"
        txt_path.write_text("not a pdf")
        time.sleep(0.5)

        watcher.stop()
        callback.assert_not_called()
