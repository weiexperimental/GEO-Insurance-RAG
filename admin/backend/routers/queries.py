from fastapi import APIRouter, Request
from pydantic import BaseModel
from datetime import datetime, timezone
import time

router = APIRouter(prefix="/api/queries", tags=["queries"])


class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    top_k: int | None = None
    chunk_top_k: int | None = None
    response_type: str | None = None
    enable_rerank: bool = True


@router.post("")
async def run_query(request: Request, body: QueryRequest):
    lr_svc = request.app.state.lr_service
    os_svc = request.app.state.os_service
    start = time.time()
    params = {
        k: v
        for k, v in {
            "top_k": body.top_k,
            "chunk_top_k": body.chunk_top_k,
            "response_type": body.response_type,
            "enable_rerank": body.enable_rerank,
        }.items()
        if v is not None
    }
    result = await lr_svc.query(body.query, mode=body.mode, **params)
    elapsed_ms = int((time.time() - start) * 1000)
    try:
        os_svc.save_query_history(
            {
                "query": body.query,
                "mode": body.mode,
                "response_time_ms": elapsed_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception:
        pass
    return {**result, "response_time_ms": elapsed_ms}


@router.post("/data")
async def run_query_data(request: Request, body: QueryRequest):
    lr_svc = request.app.state.lr_service
    return await lr_svc.query_data(body.query, mode=body.mode)


@router.get("/history")
def get_history(request: Request, limit: int = 50):
    os_svc = request.app.state.os_service
    return os_svc.get_query_history(limit=limit)
