from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def get_health(request: Request):
    os_svc = request.app.state.os_service
    overview = os_svc.get_system_overview()
    health = os_svc.get_cluster_health()
    nodes = os_svc.get_node_stats()
    try:
        knn = os_svc.get_knn_stats()
    except Exception:
        knn = {}
    return {"overview": overview, "cluster": health, "nodes": nodes, "knn": knn}
