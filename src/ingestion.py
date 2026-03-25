# src/ingestion.py
"""Thin ingestion service: validate → RAGAnything → enrich metadata."""
import asyncio
import logging
import shutil
import hashlib
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

from src.config import AppConfig
from src.logging_service import RAGLogger
from src.metadata import extract_metadata
from src.rag import RAGEngine


RETRY_DELAYS = [5, 15, 45]


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
    patterns = [
        f"{stem}/hybrid_auto/{stem}.md",
        f"{stem}/auto/{stem}.md",
        f"{stem}/{stem}.md",
        f"{stem}.md",
    ]
    for pattern in patterns:
        md_path = Path(output_dir) / pattern
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
    return ""


def _file_doc_id(file_path: str) -> str:
    """Generate deterministic doc ID from file content (MD5, matching LightRAG doc- prefix)."""
    content_hash = hashlib.md5(Path(file_path).read_bytes()).hexdigest()
    return f"doc-{content_hash}"


def validate_file(file_path: str, max_size_mb: int) -> dict[str, Any]:
    """Validate that file is a PDF within size limits."""
    path = Path(file_path)
    if not path.suffix.lower() == ".pdf":
        return {"valid": False, "reason": f"Not a PDF file: {path.suffix}"}
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        return {"valid": False, "reason": f"File size {size_mb:.1f}MB exceeds limit of {max_size_mb}MB"}
    return {"valid": True, "reason": ""}


class IngestionService:
    """Thin wrapper: validate → RAGAnything → enrich metadata."""

    def __init__(self, config: AppConfig, rag_engine: RAGEngine, logger: RAGLogger):
        self._config = config
        self._rag = rag_engine
        self._logger = logger
        self._lock = asyncio.Lock()
        self._processing: set[str] = set()  # in-memory dedup guard

        # Gateway callback config
        self._gateway_port = config.callback.gateway_port
        self._hooks_token = config.callback.hooks_token
        self._notify_to = config.callback.notify_to
        try:
            import aiohttp  # noqa: F401
            self._callback_enabled = bool(self._hooks_token)
        except ImportError:
            self._callback_enabled = False

    async def ingest(self, file_path: str) -> dict[str, Any]:
        """Ingest a single PDF. Three-layer dedup + sequential GPU lock."""
        canonical = str(Path(file_path).resolve())

        # Layer 1: In-memory guard — reject if already in-flight
        # (safe in asyncio single-thread: no await between check and add)
        if canonical in self._processing:
            return {"status": "skipped", "reason": "already_processing"}

        # Layer 2: doc_status pre-check — skip if already completed
        try:
            doc_id = _file_doc_id(canonical)
            existing = await self._rag.doc_status.get_by_id(doc_id)
            if existing and existing.get("status") == "processed":
                return {"status": "skipped", "reason": "already_processed"}
        except FileNotFoundError:
            # File already gone — will be caught by Layer 3
            pass
        except Exception:
            pass  # OpenSearch unavailable — proceed with ingestion

        self._processing.add(canonical)
        try:
            async with self._lock:
                # Layer 3: Re-check file exists (may have been moved by concurrent ingest)
                if not Path(canonical).exists():
                    return {"status": "skipped", "reason": "file_moved"}
                return await self._ingest_single(canonical)
        finally:
            self._processing.discard(canonical)

    async def _ingest_single(self, file_path: str) -> dict[str, Any]:
        file_path = str(Path(file_path).resolve())
        file_name = Path(file_path).name
        doc_id = _file_doc_id(file_path)

        # 1. Validate
        validation = validate_file(file_path, self._config.limits.max_file_size_mb)
        if not validation["valid"]:
            shutil.move(file_path, str(Path(self._config.paths.failed_dir) / file_name))
            self._logger.log(document=file_name, stage="validate", status="failed",
                             details={"reason": validation["reason"]})
            return {"error": "validation_failed", "reason": validation["reason"]}

        # 2. Ingest via RAGAnything (with retry)
        try:
            await _retry_async(lambda: self._rag.ingest_document(
                file_path=file_path,
                output_dir=self._config.paths.processed_dir,
                device=self._config.mineru.device,
                lang=self._config.mineru.lang,
                doc_id=doc_id,
            ))
        except Exception as e:
            shutil.move(file_path, str(Path(self._config.paths.failed_dir) / file_name))
            self._logger.log(document=file_name, stage="ingest", status="failed",
                             details={"error": str(e)})
            return {"error": "ingestion_failed", "reason": str(e)}

        # 3. Look up LightRAG doc_status record (doc_id is deterministic, so get_by_id is reliable)
        doc = await self._rag.doc_status.get_by_id(doc_id)

        # 4. Extract metadata from parsed content
        parsed_content = _read_parsed_content(self._config.paths.processed_dir, file_name)
        try:
            metadata = await extract_metadata(parsed_content, self._config.llm, file_name=file_name)
        except Exception:
            metadata = {}

        # 5. Enrich doc_status with metadata (read-spread-write)
        if doc:
            try:
                await self._rag.doc_status.upsert({
                    doc_id: {
                        **doc,
                        "status": "processed",
                        "metadata": {
                            **doc.get("metadata", {}),
                            **metadata,
                            "file_name": file_name,
                        },
                    }
                })
            except Exception as e:
                _logger.warning("Failed to enrich doc_status: %s", e)

        # 6. Move file
        dest = Path(self._config.paths.processed_dir) / file_name
        if Path(file_path).exists() and not dest.exists():
            shutil.move(file_path, str(dest))

        # 7. Log + notify
        self._logger.log(document=file_name, stage="complete", status="success")
        await self._notify_gateway(doc_id, file_name, "processed")

        return {"doc_id": doc_id, "status": "processed", "metadata": metadata}

    async def _notify_gateway(self, doc_id: str, file_name: str, status: str):
        """Notify OpenClaw gateway that ingestion completed."""
        if not self._callback_enabled:
            return
        import aiohttp
        url = f"http://127.0.0.1:{self._gateway_port}/hooks/wake"
        payload = {
            "text": (
                f"[入庫回調] {file_name} 完成，狀態：{status}，"
                f"document_id: {doc_id}。按 HEARTBEAT.md 嘅「回調處理」流程執行。"
            ),
            "mode": "now",
        }
        headers = {"Authorization": f"Bearer {self._hooks_token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        _logger.warning("Gateway callback failed: HTTP %d", resp.status)
        except Exception as e:
            _logger.warning("Gateway callback error: %s", e)
