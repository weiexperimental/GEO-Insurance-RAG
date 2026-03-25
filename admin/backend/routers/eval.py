from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/eval", tags=["eval"])


class CreateQAPairBody(BaseModel):
    question: str
    expected_answer: str
    source_doc: str = ""
    category: str = "product_detail"
    difficulty: str = "simple"


class UpdateQAPairBody(BaseModel):
    question: str | None = None
    expected_answer: str | None = None
    source_doc: str | None = None
    category: str | None = None
    difficulty: str | None = None
    status: str | None = None


class BatchStatusBody(BaseModel):
    qa_ids: list[str]
    status: str


class GenerateBody(BaseModel):
    doc_id: str | None = None
    count: int = 10


# IMPORTANT: /batch-status MUST be before /{qa_id}

@router.get("/qa-pairs")
def list_qa_pairs(
    request: Request,
    category: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    svc = request.app.state.eval_service
    return svc.list_qa_pairs(category, status, search, page, size)


@router.post("/qa-pairs")
def create_qa_pair(request: Request, body: CreateQAPairBody):
    svc = request.app.state.eval_service
    return svc.create_qa_pair(
        question=body.question,
        expected_answer=body.expected_answer,
        source_doc=body.source_doc,
        category=body.category,
        difficulty=body.difficulty,
    )


@router.post("/qa-pairs/batch-status")
def batch_status(request: Request, body: BatchStatusBody):
    svc = request.app.state.eval_service
    return svc.batch_update_status(body.qa_ids, body.status)


@router.put("/qa-pairs/{qa_id}")
def update_qa_pair(request: Request, qa_id: str, body: UpdateQAPairBody):
    svc = request.app.state.eval_service
    return svc.update_qa_pair(qa_id, body.model_dump(exclude_none=True))


@router.delete("/qa-pairs/{qa_id}")
def delete_qa_pair(request: Request, qa_id: str):
    svc = request.app.state.eval_service
    if not svc.delete_qa_pair(qa_id):
        raise HTTPException(404, "QA pair not found")
    return {"deleted": True}


@router.post("/generate")
async def generate_qa_pairs(request: Request, body: GenerateBody = GenerateBody()):
    svc = request.app.state.eval_service
    return await svc.generate_qa_pairs(doc_id=body.doc_id, count=body.count)


@router.post("/run")
async def run_evaluation(request: Request):
    svc = request.app.state.eval_service
    return await svc.run_evaluation()


@router.get("/runs")
def list_eval_runs(request: Request):
    svc = request.app.state.eval_service
    return svc.list_eval_runs()


@router.get("/runs/{run_id}")
def get_eval_run(request: Request, run_id: str):
    svc = request.app.state.eval_service
    run = svc.get_eval_run(run_id)
    if not run:
        raise HTTPException(404, "Eval run not found")
    return run
