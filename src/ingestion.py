# src/ingestion.py
import asyncio
import hashlib
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.logging_service import RAGLogger
from src.metadata import extract_metadata
from src.rag import RAGEngine
from src.versioning import find_existing_version


def validate_file(file_path: str, max_size_mb: int) -> dict[str, Any]:
    """Validate that file is a PDF within size limits."""
    path = Path(file_path)
    if not path.suffix.lower() == ".pdf":
        return {"valid": False, "reason": f"Not a PDF file: {path.suffix}"}

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        return {"valid": False, "reason": f"File size {size_mb:.1f}MB exceeds limit of {max_size_mb}MB"}

    return {"valid": True, "reason": ""}


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


RETRY_DELAYS = [5, 15, 45]  # Exponential backoff in seconds


async def _retry_async(coro_factory, retries=3, delays=RETRY_DELAYS):
    """Retry an async operation with exponential backoff."""
    last_error = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                await asyncio.sleep(delays[attempt])
    raise last_error


def _read_parsed_content(output_dir: str, file_name: str) -> str:
    """Read the markdown output from MinerU parsing."""
    stem = Path(file_name).stem
    for pattern in [f"{stem}/{stem}.md", f"{stem}.md", f"{stem}/auto/{stem}.md"]:
        md_path = Path(output_dir) / pattern
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
    return ""


class IngestionPipeline:
    def __init__(self, config: AppConfig, rag_engine: RAGEngine, logger: RAGLogger):
        self._config = config
        self._rag = rag_engine
        self._logger = logger
        self._queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._doc_statuses: dict[str, dict] = {}
        self._known_hashes: set[str] = set()

    def get_status(self, document_id: str) -> dict | None:
        return self._doc_statuses.get(document_id)

    def get_all_statuses(self) -> dict[str, dict]:
        return dict(self._doc_statuses)

    async def enqueue(self, file_path: str) -> dict[str, Any]:
        doc_id = str(uuid.uuid4())
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

    async def process_queue(self) -> None:
        async with self._lock:
            while not self._queue.empty():
                doc_id, file_path = await self._queue.get()
                await self._process_single(doc_id, file_path)

    async def _process_single(self, doc_id: str, file_path: str) -> None:
        from datetime import datetime, timezone
        status = self._doc_statuses[doc_id]
        file_name = Path(file_path).name
        is_reprocess = False

        # Stage: validating
        status["status"] = "validating"
        start = time.time()
        validation = validate_file(file_path, self._config.limits.max_file_size_mb)
        elapsed = int((time.time() - start) * 1000)
        status["stages"].append({"stage": "validating", "status": "success" if validation["valid"] else "failed", "duration_ms": elapsed, "error": validation.get("reason") or None})

        if not validation["valid"]:
            status["status"] = "failed"
            shutil.move(file_path, str(Path(self._config.paths.failed_dir) / file_name))
            self._logger.log(document=file_name, stage="validating", status="failed", details={"reason": validation["reason"]})
            return

        # Duplicate check
        file_hash = compute_file_hash(file_path)
        status["file_hash"] = file_hash

        if file_hash in self._known_hashes:
            existing = next((s for s in self._doc_statuses.values() if s.get("file_hash") == file_hash and s["document_id"] != doc_id), None)
            if existing and existing.get("status") == "partial":
                is_reprocess = True
            elif existing:
                status["status"] = "failed"
                status["stages"].append({"stage": "duplicate_check", "status": "skipped", "duration_ms": 0, "error": "Duplicate file"})
                self._logger.log(document=file_name, stage="duplicate_check", status="skipped", details={"reason": "duplicate"})
                return

        self._known_hashes.add(file_hash)

        # Stage: parsing (with retry)
        status["status"] = "parsing"
        start = time.time()
        try:
            await _retry_async(lambda: self._rag.ingest_document(
                file_path=file_path,
                output_dir=self._config.paths.processed_dir,
                device=self._config.mineru.device,
                lang=self._config.mineru.lang,
            ))
            elapsed = int((time.time() - start) * 1000)
            status["stages"].append({"stage": "parsing", "status": "success", "duration_ms": elapsed, "error": None})
            self._logger.log(document=file_name, stage="parsing", status="success", duration_ms=elapsed)
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            status["stages"].append({"stage": "parsing", "status": "failed", "duration_ms": elapsed, "error": str(e)})
            status["status"] = "failed"
            shutil.move(file_path, str(Path(self._config.paths.failed_dir) / file_name))
            self._logger.log(document=file_name, stage="parsing", status="failed", duration_ms=elapsed, details={"error": str(e)})
            return

        # Stage: extracting_metadata (with retry)
        status["status"] = "extracting_metadata"
        start = time.time()
        parsed_content = _read_parsed_content(self._config.paths.processed_dir, file_name)
        try:
            metadata = await _retry_async(lambda: extract_metadata(parsed_content, self._config.llm))
        except Exception:
            metadata = {}
        elapsed = int((time.time() - start) * 1000)

        if metadata:
            status["metadata"] = metadata
            status["stages"].append({"stage": "extracting_metadata", "status": "success", "duration_ms": elapsed, "error": None})
            self._logger.log(document=file_name, stage="extracting_metadata", status="success", duration_ms=elapsed, details=metadata)
        else:
            status["metadata"] = {}
            status["stages"].append({"stage": "extracting_metadata", "status": "failed", "duration_ms": elapsed, "error": "Metadata extraction failed"})
            status["status"] = "partial"
            status["ingested_at"] = datetime.now(timezone.utc).isoformat()
            self._logger.log(document=file_name, stage="extracting_metadata", status="failed", duration_ms=elapsed)
            shutil.move(file_path, str(Path(self._config.paths.processed_dir) / file_name))
            return

        # Stage: checking_version (skip for re-processed partial docs)
        if not is_reprocess and metadata:
            status["status"] = "checking_version"
            existing_docs = [s for s in self._doc_statuses.values()
                            if s["status"] in ("ready",) and s["document_id"] != doc_id]
            match = find_existing_version(metadata, [s.get("metadata", {}) | {"document_id": s["document_id"]} for s in existing_docs if s.get("metadata")])
            if match:
                status["status"] = "awaiting_confirmation"
                status["stages"].append({"stage": "checking_version", "status": "awaiting_confirmation", "duration_ms": 0, "error": None})
                status["metadata"]["_matched_doc_id"] = match["document_id"]
                self._logger.log(document=file_name, stage="checking_version", status="awaiting_confirmation",
                                details={"matched": match["document_id"]})
                return
            else:
                status["stages"].append({"stage": "checking_version", "status": "no_match", "duration_ms": 0, "error": None})

        # Stage: complete
        status["status"] = "ready"
        status["metadata"]["is_latest"] = True
        status["ingested_at"] = datetime.now(timezone.utc).isoformat()
        shutil.move(file_path, str(Path(self._config.paths.processed_dir) / file_name))
        self._logger.log(document=file_name, stage="complete", status="success")
