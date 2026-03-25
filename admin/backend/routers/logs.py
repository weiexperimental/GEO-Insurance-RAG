import os
import json
import re
from fastapi import APIRouter, Request, Query

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/dates")
def list_log_dates(request: Request):
    log_dir = request.app.state.settings.log_dir
    if not os.path.isdir(log_dir):
        return []
    files = sorted(
        [f for f in os.listdir(log_dir) if f.startswith("rag-") and f.endswith(".log")],
        reverse=True,
    )
    return [f.replace("rag-", "").replace(".log", "") for f in files]


@router.get("/{date}")
def get_logs(request: Request, date: str, limit: int = Query(500, ge=1, le=5000)):
    log_dir = request.app.state.settings.log_dir
    log_file = os.path.join(log_dir, f"rag-{date}.log")
    if not os.path.exists(log_file):
        return {"entries": [], "total": 0}
    entries = []
    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    entries.append({"raw": line})
    return {"entries": entries[-limit:], "total": len(entries)}


@router.get("/{date}/search")
def search_logs(request: Request, date: str, q: str = Query(..., min_length=1)):
    log_dir = request.app.state.settings.log_dir
    log_file = os.path.join(log_dir, f"rag-{date}.log")
    if not os.path.exists(log_file):
        return {"entries": [], "total": 0}
    pattern = re.compile(re.escape(q), re.IGNORECASE)
    entries = []
    with open(log_file, "r") as f:
        for line in f:
            if pattern.search(line):
                line = line.strip()
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    entries.append({"raw": line})
    return {"entries": entries, "total": len(entries)}
