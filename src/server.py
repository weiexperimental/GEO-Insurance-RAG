# src/server.py
import asyncio
import sys
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastmcp import FastMCP

from src.config import load_config, AppConfig
from src.ingestion import IngestionService
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
_ingestion: IngestionService | None = None
_os_client = None




def _error_response(error_code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": True,
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }


@mcp.tool
async def query(
    question: str,
    mode: str = "auto",
    top_k: int = 5,
) -> dict[str, Any]:
    """Search insurance product information using semantic search and knowledge graph."""
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
                "retrieval_time_ms": elapsed,
                "documents_searched": 0,
                "knowledge_graph_entities_matched": 0,
            },
        }
    except Exception as e:
        return _error_response("INGESTION_FAILED", str(e))


@mcp.tool
async def ingest(file_path: str) -> dict[str, Any]:
    """Process a single PDF document for ingestion."""
    if not _ingestion:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    if not Path(file_path).exists():
        return _error_response("VALIDATION_FAILED", f"File not found: {file_path}")

    # Pre-check dedup
    from src.ingestion import _file_doc_id
    doc_id = _file_doc_id(str(Path(file_path).resolve()))
    try:
        existing = await _rag_engine.doc_status.get_by_id(doc_id)
        if existing and existing.get("status") == "processed":
            try:
                Path(file_path).unlink()
            except OSError:
                pass
            meta = existing.get("metadata", {})
            return {
                "status": "already_exists",
                "file": Path(file_path).name,
                "document_id": doc_id,
                "metadata": {k: v for k, v in meta.items() if k in (
                    "company", "product_name", "product_type", "document_type", "document_date"
                )},
            }
    except Exception:
        pass

    # Fire-and-forget: return immediately, process in background
    async def _bg():
        try:
            await _ingestion.ingest(file_path)
        except Exception as e:
            print(f"Ingest error [{Path(file_path).name}]: {e}", file=sys.stderr)

    asyncio.create_task(_bg())
    return {"started": True, "file": Path(file_path).name}


@mcp.tool
async def ingest_all() -> dict[str, Any]:
    """Ingest all PDF files in the inbox directory. Sequential processing."""
    if not _ingestion or not _config:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    inbox = Path(_config.paths.inbox_dir).resolve()
    files = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"] if inbox.is_dir() else []

    if not files:
        return {"total": 0, "results": []}

    # Fire-and-forget: return immediately, process all in background sequentially
    async def _bg():
        for f in files:
            try:
                await _ingestion.ingest(str(f))
            except Exception as e:
                print(f"Ingest error [{f.name}]: {e}", file=sys.stderr)

    asyncio.create_task(_bg())
    return {"total": len(files), "started": True, "files": [f.name for f in files]}


@mcp.tool
async def list_documents(
    status: str | None = None,
    company: str | None = None,
    product_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List documents with optional filters. Reads from LightRAG doc_status."""
    if not _os_client:
        return _error_response("OPENSEARCH_UNAVAILABLE", "OpenSearch not connected")

    query_parts = []
    if status:
        query_parts.append({"term": {"status": status}})
    if company:
        query_parts.append({"match": {"metadata.company": company}})
    if product_type:
        query_parts.append({"term": {"metadata.product_type.keyword": product_type}})

    body = {
        "query": {"bool": {"must": query_parts}} if query_parts else {"match_all": {}},
        "sort": [{"updated_at": {"order": "desc"}}],
        "from": offset,
        "size": limit,
    }
    resp = _os_client.search(index="doc_status", body=body)
    documents = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        meta = src.get("metadata") or {}
        documents.append({
            "document_id": hit["_id"],
            "file_name": meta.get("file_name") or src.get("file_path", ""),
            "status": src.get("status", ""),
            "metadata": {k: v for k, v in meta.items() if k in (
                "company", "product_name", "product_type", "document_type", "document_date"
            )},
            "chunks_count": src.get("chunks_count"),
            "created_at": src.get("created_at"),
            "updated_at": src.get("updated_at"),
        })
    return {
        "documents": documents,
        "total": resp["hits"]["total"]["value"],
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
    """System health and document counts."""
    result = {"opensearch": {}, "documents": {}, "inbox": {}}

    # OpenSearch health
    try:
        health = _os_client.cluster.health()
        result["opensearch"]["status"] = health.get("status", "unknown")
    except Exception:
        result["opensearch"]["status"] = "disconnected"

    # Document counts from doc_status
    try:
        counts = await _rag_engine.doc_status.get_all_status_counts()
        result["documents"] = counts
    except Exception:
        result["documents"] = {}

    # Inbox
    try:
        inbox = Path(_config.paths.inbox_dir).resolve()
        files = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"] if inbox.is_dir() else []
        result["inbox"]["pending_files"] = len(files)
    except Exception:
        result["inbox"]["pending_files"] = 0

    return result


async def _initialize():
    """Initialize all components with OpenSearch health check retry."""
    global _config, _rag_engine, _logger, _ingestion, _os_client

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
                print("WARNING: OpenSearch not available, starting in degraded mode", file=sys.stderr)

    _rag_engine = RAGEngine(
        llm_config=_config.llm,
        embedding_config=_config.embedding,
        vision_config=_config.vision,
        opensearch_config=_config.opensearch,
        working_dir="./rag_working_dir",
    )
    await _rag_engine.initialize()  # fail hard — no point running with broken RAG

    _ingestion = IngestionService(
        config=_config, rag_engine=_rag_engine, logger=_logger,
    )


if __name__ == "__main__":
    mcp.run()
