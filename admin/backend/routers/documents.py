from fastapi import APIRouter, Request, UploadFile, File, Query, HTTPException

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
):
    os_svc = request.app.state.os_service
    return os_svc.get_ingestion_statuses(limit=limit, offset=offset, status_filter=status)


@router.get("/analytics")
def get_analytics(request: Request):
    os_svc = request.app.state.os_service
    return os_svc.get_ingestion_analytics()


@router.get("/chunk-counts")
def chunk_counts(request: Request):
    return request.app.state.os_service.get_chunk_counts()


@router.get("/{doc_id}/detail")
def document_detail(request: Request, doc_id: str):
    os_svc = request.app.state.os_service
    # Get document
    try:
        doc = os_svc._client.get(index="doc_status", id=doc_id)
    except Exception:
        raise HTTPException(404, "Document not found")

    # Get chunk stats for this document
    chunk_count = 0
    chunk_types: dict = {}
    try:
        body = {
            "query": {"term": {"full_doc_id.keyword": doc_id}},
            "size": 0,
            "aggs": {
                "by_type": {"terms": {"field": "original_type.keyword", "size": 20}},
                "total_tokens": {"sum": {"field": "tokens"}}
            }
        }
        resp = os_svc._client.search(index="text_chunks", body=body)
        chunk_count = resp["hits"]["total"]["value"]
        chunk_types = {b["key"]: b["doc_count"] for b in resp["aggregations"]["by_type"]["buckets"]}
    except Exception:
        pass

    # Get entity count for this document
    entity_count = 0
    try:
        file_path = doc["_source"].get("file_path", "")
        if file_path:
            body = {"query": {"match": {"file_path": file_path}}, "size": 0}
            resp = os_svc._client.search(index="chunk_entity_relation-nodes", body=body)
            entity_count = resp["hits"]["total"]["value"]
    except Exception:
        pass

    translated = os_svc._translate(doc)
    translated["chunk_count"] = chunk_count
    translated["chunk_types"] = chunk_types
    translated["entity_count"] = entity_count
    return translated


@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    # Ingestion is handled via MCP server (Katrina calls ingest tool).
    # Admin dashboard does not ingest directly.
    raise HTTPException(501, "Use MCP server ingest tool via Katrina. Admin dashboard does not support direct upload.")


@router.post("/scan")
async def scan_inbox(request: Request):
    raise HTTPException(501, "Use MCP server ingest_all tool via Katrina. Admin dashboard does not support direct scan.")


@router.delete("/{doc_id}")
async def delete_document(request: Request, doc_id: str):
    lightrag = getattr(request.app.state, 'graph_service', None)
    lr = lightrag._lr if lightrag else None
    if lr:
        try:
            await lr.adelete_by_doc_id(doc_id)
            return {"deleted": True, "doc_id": doc_id}
        except Exception as e:
            raise HTTPException(500, f"Delete failed: {e}")
    else:
        # Fallback: just delete from doc_status
        os_svc = request.app.state.os_service
        try:
            os_svc._client.delete(index="doc_status", id=doc_id)
            return {"deleted": True, "doc_id": doc_id, "warning": "Only doc_status deleted, LightRAG not available"}
        except Exception:
            raise HTTPException(404, f"Document not found: {doc_id}")


@router.post("/reprocess")
async def reprocess_failed(request: Request):
    raise HTTPException(501, "Use MCP server ingest tool to re-ingest failed documents.")
