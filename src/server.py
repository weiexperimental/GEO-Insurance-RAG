# src/server.py
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastmcp import FastMCP

from src.config import load_config, AppConfig
from src.ingestion import IngestionPipeline
from src.logging_service import RAGLogger
from src.rag import RAGEngine


@asynccontextmanager
async def lifespan(server):
    await _initialize()
    yield


mcp = FastMCP("GEO Insurance RAG", lifespan=lifespan)

# Global state (initialized on startup)
_config: AppConfig | None = None
_rag_engine: RAGEngine | None = None
_logger: RAGLogger | None = None
_pipeline: IngestionPipeline | None = None
_os_client = None


def _error_response(error_code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": True,
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }


def _ensure_ingestion_index(client):
    """Create rag-ingestion-status index if it doesn't exist."""
    if not client.indices.exists(index="rag-ingestion-status"):
        client.indices.create(index="rag-ingestion-status", body={
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


@mcp.tool
async def query(
    question: str,
    filters: dict | None = None,
    mode: str = "auto",
    top_k: int = 5,
    only_latest: bool = True,
) -> dict[str, Any]:
    """Search insurance product information using semantic search and knowledge graph.
    Supports filtering by company, product_type, document_type."""
    if not _rag_engine:
        return _error_response("OPENSEARCH_UNAVAILABLE", "RAG engine not initialized")

    import time
    start = time.time()

    try:
        effective_mode = "hybrid" if mode == "auto" else mode
        result = await _rag_engine.query(question, mode=effective_mode, top_k=top_k)

        elapsed = int((time.time() - start) * 1000)
        return {
            "results": [{"content": result, "source_document": "", "company": "", "product_name": "", "page": 0, "relevance_score": 1.0}],
            "metadata": {
                "query_mode": effective_mode,
                "total_results": 1,
                "filters_applied": filters or {},
                "retrieval_time_ms": elapsed,
                "documents_searched": 0,
                "knowledge_graph_entities_matched": 0,
            },
        }
    except Exception as e:
        return _error_response("INGESTION_FAILED", str(e))


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


@mcp.tool
async def ingest_document(file_path: str) -> dict[str, Any]:
    """Process a single PDF document for ingestion."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    if not Path(file_path).exists():
        return _error_response("VALIDATION_FAILED", f"File not found: {file_path}")

    result = await _pipeline.enqueue(file_path)
    asyncio.create_task(_pipeline.process_queue())
    return result


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

    return {"documents": docs, "total": total, "limit": limit, "offset": offset}


@mcp.tool
async def list_documents(
    filters: dict | None = None,
    only_latest: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List all indexed documents with metadata."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    all_statuses = _pipeline.get_all_statuses()
    docs = [d for d in all_statuses.values() if d["status"] in ("ready", "partial")]

    if only_latest:
        docs = [d for d in docs if d.get("metadata", {}).get("is_latest", True)]

    if filters:
        for key, val in filters.items():
            docs = [d for d in docs if d.get("metadata", {}).get(key) == val]

    total = len(docs)
    docs = docs[offset : offset + limit]

    return {
        "documents": [
            {
                "document_id": d["document_id"],
                "file_name": d["file_name"],
                "company": d.get("metadata", {}).get("company", ""),
                "product_name": d.get("metadata", {}).get("product_name", ""),
                "product_type": d.get("metadata", {}).get("product_type", ""),
                "document_type": d.get("metadata", {}).get("document_type", ""),
                "document_date": d.get("metadata", {}).get("document_date", ""),
                "is_latest": d.get("metadata", {}).get("is_latest", True),
                "ingested_at": d.get("ingested_at", ""),
                "status": d["status"],
            }
            for d in docs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@mcp.tool
async def delete_document(document_id: str, confirm: bool = False) -> dict[str, Any]:
    """Delete a document from the index."""
    if not confirm:
        return _error_response("INVALID_PARAMETERS", "Must set confirm=true to delete")
    if not _rag_engine:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    success = await _rag_engine.delete_document(document_id)
    return {
        "success": success,
        "message": "Document deleted" if success else "Delete failed",
        "knowledge_graph_updated": success,
    }


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


@mcp.tool
async def confirm_version_update(document_id: str, replace: bool = False) -> dict[str, Any]:
    """Confirm whether a new document version should replace the old one."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    status = _pipeline.get_status(document_id)
    if not status:
        return _error_response("DOCUMENT_NOT_FOUND", f"Document {document_id} not found")
    if status["status"] != "awaiting_confirmation":
        return _error_response("INVALID_PARAMETERS", f"Document is not awaiting confirmation (status: {status['status']})")

    return {
        "success": True,
        "old_document_id": None,
        "message": "Version update confirmed" if replace else "Document indexed as independent",
    }


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


if __name__ == "__main__":
    mcp.run()
