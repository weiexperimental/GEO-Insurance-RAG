from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/graph", tags=["graph"])

class EditEntityBody(BaseModel):
    updates: dict

class MergeEntitiesBody(BaseModel):
    source_entities: list[str]
    target_entity: str

class EditRelationBody(BaseModel):
    source: str
    target: str
    updates: dict

class DeleteRelationBody(BaseModel):
    source: str
    target: str

@router.get("")
def get_graph(request: Request, types: str = Query(""), doc: str = Query(""), max_nodes: int = Query(200, ge=1, le=2000)):
    svc = request.app.state.graph_service
    type_filter = [t.strip() for t in types.split(",") if t.strip()] or None
    return svc.get_graph(type_filter=type_filter, doc_filter=doc or None, max_nodes=max_nodes)

@router.get("/search")
def search_entities(request: Request, q: str = Query(..., min_length=1), limit: int = Query(20)):
    return request.app.state.graph_service.search_entities(q, limit)

@router.get("/popular")
def popular_entities(request: Request, limit: int = Query(20)):
    return request.app.state.graph_service.get_popular_entities(limit)

@router.get("/entity/{entity_id:path}")
def entity_detail(request: Request, entity_id: str):
    return request.app.state.graph_service.get_entity_detail(entity_id)

@router.get("/edge")
def edge_detail(request: Request, source: str = Query(...), target: str = Query(...)):
    return request.app.state.graph_service.get_edge_detail(source, target) or {"error": "Edge not found"}

@router.get("/similar/{entity_id:path}")
def similar_entities(request: Request, entity_id: str, limit: int = Query(10, ge=1, le=50)):
    return request.app.state.graph_service.find_similar_entities(entity_id, limit)

@router.post("/entity/{entity_id:path}/edit")
async def edit_entity(request: Request, entity_id: str, body: EditEntityBody):
    return await request.app.state.graph_service.edit_entity(entity_id, body.updates)

@router.delete("/entity/{entity_id:path}")
async def delete_entity(request: Request, entity_id: str):
    return await request.app.state.graph_service.delete_entity(entity_id)

@router.post("/entity/merge")
async def merge_entities(request: Request, body: MergeEntitiesBody):
    return await request.app.state.graph_service.merge_entities(body.source_entities, body.target_entity)

@router.post("/relation/edit")
async def edit_relation(request: Request, body: EditRelationBody):
    return await request.app.state.graph_service.edit_relation(body.source, body.target, body.updates)

@router.delete("/relation")
async def delete_relation(request: Request, body: DeleteRelationBody):
    return await request.app.state.graph_service.delete_relation(body.source, body.target)
