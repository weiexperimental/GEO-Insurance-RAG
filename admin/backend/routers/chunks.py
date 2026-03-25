from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/chunks", tags=["chunks"])


class UpdateChunkBody(BaseModel):
    content: str


class BatchDeleteBody(BaseModel):
    chunk_ids: list[str]


# IMPORTANT: /stats and /token-distribution MUST be before /{chunk_id}

@router.get("")
def list_chunks(
    request: Request,
    doc_id: str | None = Query(None),
    type: str | None = Query(None),
    quality: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    svc = request.app.state.chunk_service
    return svc.list_chunks(doc_id, type, quality, search, page, size)


@router.get("/stats")
def quality_stats(request: Request, doc_id: str | None = Query(None)):
    return request.app.state.chunk_service.get_quality_stats(doc_id)


@router.get("/token-distribution")
def token_distribution(request: Request, doc_id: str | None = Query(None)):
    return request.app.state.chunk_service.get_token_distribution(doc_id)


@router.get("/{chunk_id}")
def get_chunk(request: Request, chunk_id: str):
    chunk = request.app.state.chunk_service.get_chunk(chunk_id)
    if not chunk:
        raise HTTPException(404, "Chunk not found")
    return chunk


@router.put("/{chunk_id}")
async def update_chunk(request: Request, chunk_id: str, body: UpdateChunkBody):
    return await request.app.state.chunk_service.update_chunk(chunk_id, body.content)


@router.delete("/{chunk_id}")
def delete_chunk(request: Request, chunk_id: str):
    if not request.app.state.chunk_service.delete_chunk(chunk_id):
        raise HTTPException(404, "Chunk not found in any index")
    return {"deleted": True}


@router.post("/batch-delete")
def batch_delete(request: Request, body: BatchDeleteBody):
    return request.app.state.chunk_service.batch_delete(body.chunk_ids)
