from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/playground", tags=["playground"])


def _get_service(request: Request):
    svc = request.app.state.playground_service
    if svc is None:
        raise HTTPException(503, "Query playground unavailable — LightRAG not initialized")
    return svc


class QueryBody(BaseModel):
    query: str
    mode: Literal["local", "global", "hybrid", "naive", "mix"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50)
    chunk_top_k: int = Field(default=10, ge=1, le=100)
    enable_rerank: bool = True


class QueryParams(BaseModel):
    mode: Literal["local", "global", "hybrid", "naive", "mix"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50)
    chunk_top_k: int = Field(default=10, ge=1, le=100)
    enable_rerank: bool = True


class CompareBody(BaseModel):
    query: str
    params_a: QueryParams
    params_b: QueryParams


@router.post("/query")
async def playground_query(request: Request, body: QueryBody):
    svc = _get_service(request)
    return await svc.query_full(
        body.query, mode=body.mode, top_k=body.top_k,
        chunk_top_k=body.chunk_top_k, enable_rerank=body.enable_rerank,
    )


@router.post("/retrieve-only")
async def playground_retrieve_only(request: Request, body: QueryBody):
    svc = _get_service(request)
    return await svc.retrieve_only(
        body.query, mode=body.mode, top_k=body.top_k,
        chunk_top_k=body.chunk_top_k, enable_rerank=body.enable_rerank,
    )


@router.post("/compare")
async def playground_compare(request: Request, body: CompareBody):
    svc = _get_service(request)
    return await svc.compare(
        body.query,
        body.params_a.model_dump(),
        body.params_b.model_dump(),
    )
