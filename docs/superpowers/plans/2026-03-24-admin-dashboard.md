# Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time admin dashboard for the GEO Insurance RAG system with system monitoring, document management, knowledge graph exploration, query testing, and log viewing.

**Architecture:** FastAPI backend (thin proxy + aggregator) polls OpenSearch and LightRAG API, pushes deltas via WebSocket to a Next.js 16 frontend. All data reads go through OpenSearch directly; graph/query/document operations proxy to LightRAG API at :9621.

**Tech Stack:** FastAPI 0.135 + opensearch-py 3.1 + httpx (backend), Next.js 16.x + shadcn/ui + react-force-graph-2d + react-use-websocket + @melloware/react-logviewer (frontend), Docker Compose for orchestration.

**Spec:** `docs/superpowers/specs/2026-03-24-admin-dashboard-design.md`

**Scope:** V1 only — all 5 pages, graph read-only (no CRUD), no mode comparison, simple fetch wrapper (no OpenAPI codegen).

---

## File Structure

### Backend (`admin/backend/`)

| File | Responsibility |
|------|---------------|
| `admin/backend/pyproject.toml` | Python project config, dependencies |
| `admin/backend/main.py` | FastAPI app creation, CORS, lifespan (start poller, init clients) |
| `admin/backend/config.py` | Settings via env vars (OpenSearch host/port, LightRAG URL, log dir) |
| `admin/backend/ws.py` | WebSocket ConnectionManager — connect, disconnect, broadcast, handle sync |
| `admin/backend/poller.py` | Background asyncio task — poll data sources at intervals, compute deltas, broadcast |
| `admin/backend/routers/system.py` | `GET /api/system/health` — cluster health, node stats, k-NN stats, index stats |
| `admin/backend/routers/documents.py` | `GET /api/documents` (list), `POST /api/documents/upload`, `DELETE /api/documents/{id}`, `POST /api/documents/reprocess`, `PUT /api/documents/{id}/confirm` |
| `admin/backend/routers/graph.py` | `GET /api/graph` (subgraph), `GET /api/graph/search`, `GET /api/graph/popular` |
| `admin/backend/routers/queries.py` | `POST /api/queries` (proxy), `POST /api/queries/data` (structured), `GET /api/queries/history` |
| `admin/backend/routers/logs.py` | `GET /api/logs/dates`, `GET /api/logs/{date}`, `GET /api/logs/{date}/search` |
| `admin/backend/services/opensearch.py` | OpenSearch client wrapper — cluster health, index stats, ingestion status queries, query history CRUD |
| `admin/backend/services/lightrag.py` | httpx async client — proxy calls to LightRAG API endpoints |
| `tests/admin/conftest.py` | Shared fixtures for admin backend tests |
| `tests/admin/test_services_opensearch.py` | OpenSearch service unit tests |
| `tests/admin/test_services_lightrag.py` | LightRAG service unit tests |
| `tests/admin/test_ws.py` | WebSocket manager tests |
| `tests/admin/test_poller.py` | Poller delta detection tests |
| `tests/admin/test_routers_system.py` | System router endpoint tests |
| `tests/admin/test_routers_documents.py` | Documents router endpoint tests |
| `tests/admin/test_routers_graph.py` | Graph router endpoint tests |
| `tests/admin/test_routers_queries.py` | Queries router endpoint tests |
| `tests/admin/test_routers_logs.py` | Logs router endpoint tests |

### Frontend (`admin/frontend/`)

| File | Responsibility |
|------|---------------|
| `admin/frontend/package.json` | Node project config, dependencies |
| `admin/frontend/next.config.ts` | Next.js config (API proxy in dev) |
| `admin/frontend/next.config.ts` | Next.js config (standalone output for Docker) |
| `admin/frontend/src/app/globals.css` | Global CSS + Tailwind imports + dark theme vars |
| `admin/frontend/src/app/layout.tsx` | Root layout — dark bg, sidebar nav, WS provider |
| `admin/frontend/src/app/page.tsx` | Overview page — stat cards, system health, live feed |
| `admin/frontend/src/app/documents/page.tsx` | Documents page — table, timeline, actions, analytics |
| `admin/frontend/src/app/graph/page.tsx` | Graph page — force graph, search, popular, detail panel |
| `admin/frontend/src/app/queries/page.tsx` | Queries page — test panel, structured data, history |
| `admin/frontend/src/app/logs/page.tsx` | Logs page — stream, filter, search, date selector |
| `admin/frontend/src/hooks/use-dashboard-ws.ts` | WebSocket hook — connect, parse messages, dispatch to stores |
| `admin/frontend/src/hooks/use-api.ts` | Fetch wrapper — typed API calls with error handling |
| `admin/frontend/src/components/stats-card.tsx` | Stat card component (large number + label) |
| `admin/frontend/src/components/live-feed.tsx` | Terminal-style ingestion feed |
| `admin/frontend/src/components/system-health.tsx` | System health bar |
| `admin/frontend/src/components/doc-table.tsx` | Document table with sorting/filtering |
| `admin/frontend/src/components/stage-timeline.tsx` | Ingestion stage timeline per document |
| `admin/frontend/src/components/graph-viewer.tsx` | react-force-graph-2d wrapper |
| `admin/frontend/src/components/node-detail.tsx` | Graph node detail panel |
| `admin/frontend/src/components/query-panel.tsx` | Query input + streaming response |
| `admin/frontend/src/components/log-viewer.tsx` | @melloware/react-logviewer wrapper |
| `admin/frontend/src/components/nav.tsx` | Top navigation tabs |
| `admin/frontend/src/lib/types.ts` | TypeScript type definitions for API responses |

### Infrastructure

| File | Responsibility |
|------|---------------|
| `docker/docker-compose.yml` | Updated — add lightrag-api, admin-backend, admin-frontend services; fix port bindings |
| `.gitignore` | Add `.superpowers/`, `admin/frontend/node_modules/`, `admin/frontend/.next/` |

---

## Task 0: Prerequisites

**Files:**
- Modify: `docker/docker-compose.yml`
- Modify: `.gitignore`

- [ ] **Step 1: Fix OpenSearch port bindings**

In `docker/docker-compose.yml`, change:
```yaml
    ports:
      - "127.0.0.1:9200:9200"
```
and:
```yaml
    ports:
      - "127.0.0.1:5601:5601"
```

- [ ] **Step 2: Fix rag-ingestion-status replica count**

Run:
```bash
curl -X PUT "http://localhost:9200/rag-ingestion-status/_settings" \
  -H 'Content-Type: application/json' \
  -d '{"index": {"number_of_replicas": 0}}'
```
Expected: `{"acknowledged": true}`

Verify:
```bash
curl -s "http://localhost:9200/_cat/indices/rag-ingestion-status?v"
```
Expected: health = `green`

- [ ] **Step 3: Update .gitignore**

Add these lines to `.gitignore`:
```
.superpowers/
admin/frontend/node_modules/
admin/frontend/.next/
```

- [ ] **Step 4: Commit**

```bash
git add docker/docker-compose.yml .gitignore
git commit -m "chore: fix OpenSearch port bindings and gitignore for admin dashboard"
```

---

## Task 1: Backend Project Setup + Config

**Files:**
- Create: `admin/backend/pyproject.toml`
- Create: `admin/backend/config.py`
- Create: `admin/backend/__init__.py`
- Create: `admin/backend/routers/__init__.py`
- Create: `admin/backend/services/__init__.py`
- Create: `tests/admin/__init__.py`
- Create: `tests/admin/conftest.py`
- Test: `tests/admin/test_config.py`

- [ ] **Step 1: Create backend directory structure**

```bash
mkdir -p admin/backend/routers admin/backend/services tests/admin
touch admin/backend/__init__.py admin/backend/routers/__init__.py admin/backend/services/__init__.py tests/admin/__init__.py
```

- [ ] **Step 2: Write pyproject.toml**

Create `admin/backend/pyproject.toml`:
```toml
[project]
name = "admin-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "opensearch-py>=3.1.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.28.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["../../tests/admin"]
```

- [ ] **Step 3: Write config.py**

Create `admin/backend/config.py`:
```python
from dataclasses import dataclass, field
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    lightrag_api_url: str = "http://localhost:9621"
    log_dir: str = "./logs"
    host: str = "0.0.0.0"
    port: int = 8080


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        opensearch_host=os.getenv("OPENSEARCH_HOST", "localhost"),
        opensearch_port=int(os.getenv("OPENSEARCH_PORT", "9200")),
        lightrag_api_url=os.getenv("LIGHTRAG_API_URL", "http://localhost:9621"),
        log_dir=os.getenv("LOG_DIR", "./logs"),
        host=os.getenv("ADMIN_HOST", "0.0.0.0"),
        port=int(os.getenv("ADMIN_PORT", "8080")),
    )
```

- [ ] **Step 4: Write failing test**

Create `tests/admin/test_config.py`:
```python
from admin.backend.config import Settings, load_settings


def test_default_settings():
    s = Settings()
    assert s.opensearch_host == "localhost"
    assert s.opensearch_port == 9200
    assert s.lightrag_api_url == "http://localhost:9621"
    assert s.log_dir == "./logs"
    assert s.port == 8080


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_HOST", "opensearch")
    monkeypatch.setenv("OPENSEARCH_PORT", "9201")
    monkeypatch.setenv("LIGHTRAG_API_URL", "http://lightrag:9621")
    s = load_settings()
    assert s.opensearch_host == "opensearch"
    assert s.opensearch_port == 9201
    assert s.lightrag_api_url == "http://lightrag:9621"
```

Create `tests/admin/conftest.py`:
```python
# Tests rely on PYTHONPATH=admin/backend being set when running pytest.
# No sys.path manipulation needed.
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
PYTHONPATH=admin/backend python -m pytest tests/admin/test_config.py -v
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add admin/backend/ tests/admin/
git commit -m "feat(admin): backend project setup with config"
```

---

## Task 2: OpenSearch Service

**Files:**
- Create: `admin/backend/services/opensearch.py`
- Test: `tests/admin/test_services_opensearch.py`

- [ ] **Step 1: Write failing test**

Create `tests/admin/test_services_opensearch.py`:
```python
from unittest.mock import MagicMock, AsyncMock
import pytest
from services.opensearch import OpenSearchService


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.cluster.health.return_value = {"status": "green", "number_of_nodes": 1}
    client.nodes.stats.return_value = {
        "nodes": {"node1": {"jvm": {"mem": {"heap_used_percent": 67}}, "os": {"mem": {"used_percent": 33}}, "fs": {"total": {"available_in_bytes": 455_000_000_000, "total_in_bytes": 485_000_000_000}}}}
    }
    client.cat.indices.return_value = [
        {"index": "entities", "docs.count": "865", "store.size": "10.8mb", "health": "green"},
        {"index": "chunk_entity_relation-nodes", "docs.count": "865", "store.size": "409kb", "health": "green"},
    ]
    client.count.return_value = {"count": 142}
    client.search.return_value = {"hits": {"total": {"value": 3}, "hits": []}}
    return client


@pytest.fixture
def service(mock_client):
    return OpenSearchService(mock_client)


def test_get_cluster_health(service, mock_client):
    result = service.get_cluster_health()
    assert result["status"] == "green"
    mock_client.cluster.health.assert_called_once()


def test_get_node_stats(service):
    result = service.get_node_stats()
    assert "nodes" in result


def test_get_index_stats(service, mock_client):
    result = service.get_index_stats()
    assert len(result) == 2
    assert result[0]["index"] == "entities"


def test_get_doc_count(service, mock_client):
    result = service.get_doc_count("entities")
    assert result == 142


def test_get_ingestion_statuses(service, mock_client):
    mock_client.search.return_value = {
        "hits": {
            "total": {"value": 1},
            "hits": [{"_id": "doc1", "_source": {"status": "ready", "file_name": "test.pdf"}}]
        }
    }
    result = service.get_ingestion_statuses(limit=10, offset=0)
    assert result["total"] == 1


def test_get_knn_stats(service, mock_client):
    mock_client.transport.perform_request = MagicMock(return_value={"circuit_breaker_triggered": False})
    result = service.get_knn_stats()
    assert result["circuit_breaker_triggered"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_services_opensearch.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'services.opensearch'`

- [ ] **Step 3: Implement OpenSearch service**

Create `admin/backend/services/opensearch.py`:
```python
from opensearchpy import OpenSearch


class OpenSearchService:
    def __init__(self, client: OpenSearch):
        self._client = client

    def get_cluster_health(self) -> dict:
        return self._client.cluster.health()

    def get_node_stats(self) -> dict:
        return self._client.nodes.stats(metric="jvm,fs,os")

    def get_index_stats(self) -> list[dict]:
        return self._client.cat.indices(
            format="json",
            h="index,health,docs.count,docs.deleted,store.size,pri.store.size",
        )

    def get_doc_count(self, index: str) -> int:
        return self._client.count(index=index)["count"]

    def get_knn_stats(self) -> dict:
        return self._client.transport.perform_request("GET", "/_plugins/_knn/stats")

    def get_ingestion_statuses(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = None,
        sort_field: str = "ingested_at",
        sort_order: str = "desc",
    ) -> dict:
        query: dict = {"match_all": {}}
        if status_filter:
            query = {"term": {"status": status_filter}}

        body = {
            "query": query,
            "sort": [{sort_field: {"order": sort_order}}],
            "from": offset,
            "size": limit,
        }
        resp = self._client.search(index="rag-ingestion-status", body=body)
        return {
            "total": resp["hits"]["total"]["value"],
            "documents": [
                {"document_id": h["_id"], **h["_source"]}
                for h in resp["hits"]["hits"]
            ],
        }

    def get_active_ingestions(self) -> list[dict]:
        """Get documents not in terminal state (ready/failed/partial)."""
        body = {
            "query": {
                "bool": {
                    "must_not": [
                        {"terms": {"status": ["ready", "failed", "partial"]}}
                    ]
                }
            },
            "size": 100,
        }
        resp = self._client.search(index="rag-ingestion-status", body=body)
        return [{"document_id": h["_id"], **h["_source"]} for h in resp["hits"]["hits"]]

    def get_ingestion_analytics(self) -> dict:
        """Aggregate ingestion stats: avg duration per stage, status counts."""
        body = {
            "size": 0,
            "aggs": {
                "status_counts": {"terms": {"field": "status", "size": 20}},
            },
        }
        resp = self._client.search(index="rag-ingestion-status", body=body)
        return {
            "status_counts": {
                b["key"]: b["doc_count"]
                for b in resp["aggregations"]["status_counts"]["buckets"]
            },
        }

    def save_query_history(self, entry: dict) -> None:
        self._client.index(index="rag-query-history", body=entry)

    def get_query_history(self, limit: int = 50) -> list[dict]:
        try:
            resp = self._client.search(
                index="rag-query-history",
                body={"query": {"match_all": {}}, "sort": [{"timestamp": "desc"}], "size": limit},
            )
            return [h["_source"] for h in resp["hits"]["hits"]]
        except Exception:
            return []

    def get_system_overview(self) -> dict:
        """Aggregate call for overview page stats."""
        health = self.get_cluster_health()
        indices = self.get_index_stats()
        index_map = {i["index"]: i for i in indices}

        def count(name: str) -> str:
            return index_map.get(name, {}).get("docs.count", "0")

        # Calculate total index size
        total_bytes = sum(
            int(i.get("pri.store.size", "0").replace("b", "").replace("k", "000").replace("m", "000000").replace("g", "000000000"))
            for i in indices if i.get("pri.store.size")
        ) if indices else 0
        index_size = f"{total_bytes / 1e9:.1f}GB" if total_bytes > 1e9 else f"{total_bytes / 1e6:.1f}MB"

        # Get pending/failed counts from ingestion status
        analytics = self.get_ingestion_analytics()
        status_counts = analytics.get("status_counts", {})

        return {
            "cluster_status": health["status"],
            "documents": count("rag-ingestion-status"),
            "entities": count("chunk_entity_relation-nodes"),
            "relationships": count("chunk_entity_relation-edges"),
            "chunks": count("chunks"),
            "llm_cache": count("llm_response_cache"),
            "index_size": index_size,
            "pending": str(status_counts.get("pending", 0) + status_counts.get("parsing", 0) + status_counts.get("validating", 0) + status_counts.get("extracting_metadata", 0)),
            "failed": str(status_counts.get("failed", 0)),
            "total_indices": len(indices),
            "indices": indices,
        }
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_services_opensearch.py -v
```
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add admin/backend/services/opensearch.py tests/admin/test_services_opensearch.py
git commit -m "feat(admin): OpenSearch service with cluster stats and ingestion queries"
```

---

## Task 3: LightRAG Proxy Service

**Files:**
- Create: `admin/backend/services/lightrag.py`
- Test: `tests/admin/test_services_lightrag.py`

- [ ] **Step 1: Write failing test**

Create `tests/admin/test_services_lightrag.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.lightrag import LightRAGService


@pytest.fixture
def service():
    return LightRAGService("http://localhost:9621")


@pytest.mark.asyncio
async def test_get_graph(service):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"nodes": [], "edges": []}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(service._client, "get", return_value=mock_resp):
        result = await service.get_graph(label="*", max_depth=3, max_nodes=200)
        assert "nodes" in result


@pytest.mark.asyncio
async def test_search_labels(service):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ["Entity1", "Entity2"]
    mock_resp.raise_for_status = MagicMock()

    with patch.object(service._client, "get", return_value=mock_resp):
        result = await service.search_labels("test")
        assert result == ["Entity1", "Entity2"]


@pytest.mark.asyncio
async def test_get_popular_labels(service):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ["Pop1", "Pop2"]
    mock_resp.raise_for_status = MagicMock()

    with patch.object(service._client, "get", return_value=mock_resp):
        result = await service.get_popular_labels(limit=50)
        assert len(result) == 2


@pytest.mark.asyncio
async def test_query_stream(service):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "answer"}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(service._client, "post", return_value=mock_resp):
        result = await service.query("test question", mode="hybrid")
        assert result["response"] == "answer"


@pytest.mark.asyncio
async def test_get_documents_status(service):
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"busy": False, "docs": 2}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(service._client, "get", return_value=mock_resp):
        result = await service.get_pipeline_status()
        assert result["busy"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_services_lightrag.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement LightRAG service**

Create `admin/backend/services/lightrag.py`:
```python
import httpx


class LightRAGService:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def close(self):
        await self._client.aclose()

    # -- Graph --

    async def get_graph(self, label: str = "*", max_depth: int = 3, max_nodes: int = 200) -> dict:
        resp = await self._client.get(
            "/graphs", params={"label": label, "max_depth": max_depth, "max_nodes": max_nodes}
        )
        resp.raise_for_status()
        return resp.json()

    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        resp = await self._client.get("/graph/label/search", params={"q": query, "limit": limit})
        resp.raise_for_status()
        return resp.json()

    async def get_popular_labels(self, limit: int = 50) -> list[str]:
        resp = await self._client.get("/graph/label/popular", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    # -- Query --

    async def query(self, query: str, mode: str = "hybrid", **kwargs) -> dict:
        body = {"query": query, "mode": mode, **kwargs}
        resp = await self._client.post("/query", json=body)
        resp.raise_for_status()
        return resp.json()

    async def query_data(self, query: str, mode: str = "hybrid", **kwargs) -> dict:
        body = {"query": query, "mode": mode, **kwargs}
        resp = await self._client.post("/query/data", json=body)
        resp.raise_for_status()
        return resp.json()

    # -- Documents --

    async def upload_document(self, file_bytes: bytes, filename: str) -> dict:
        files = {"files": (filename, file_bytes, "application/pdf")}
        resp = await self._client.post("/documents/upload", files=files, timeout=120.0)
        resp.raise_for_status()
        return resp.json()

    async def scan_inbox(self) -> dict:
        resp = await self._client.post("/documents/scan", json={})
        resp.raise_for_status()
        return resp.json()

    async def delete_document(self, doc_id: str) -> dict:
        resp = await self._client.request("DELETE", f"/documents/{doc_id}", json={"doc_ids": [doc_id]})
        resp.raise_for_status()
        return resp.json()

    async def reprocess_failed(self) -> dict:
        resp = await self._client.post("/documents/reprocess_failed", json={})
        resp.raise_for_status()
        return resp.json()

    async def get_pipeline_status(self) -> dict:
        resp = await self._client.get("/documents/status")
        resp.raise_for_status()
        return resp.json()

    async def get_documents(self) -> dict:
        resp = await self._client.get("/documents")
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_services_lightrag.py -v
```
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add admin/backend/services/lightrag.py tests/admin/test_services_lightrag.py
git commit -m "feat(admin): LightRAG proxy service with graph, query, and document endpoints"
```

---

## Task 4: WebSocket Manager

**Files:**
- Create: `admin/backend/ws.py`
- Test: `tests/admin/test_ws.py`

- [ ] **Step 1: Write failing test**

Create `tests/admin/test_ws.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from ws import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.mark.asyncio
async def test_connect_adds_to_active(manager):
    ws = AsyncMock()
    await manager.connect(ws)
    assert ws in manager.active
    ws.accept.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_removes(manager):
    ws = AsyncMock()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert ws not in manager.active


@pytest.mark.asyncio
async def test_broadcast_sends_to_all(manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.broadcast({"type": "test", "data": {}})
    ws1.send_json.assert_awaited_once()
    ws2.send_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections(manager):
    ws_good = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_json.side_effect = Exception("disconnected")
    await manager.connect(ws_good)
    await manager.connect(ws_dead)
    await manager.broadcast({"type": "test", "data": {}})
    assert ws_dead not in manager.active
    assert ws_good in manager.active
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_ws.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement WebSocket manager**

Create `admin/backend/ws.py`:
```python
from fastapi import WebSocket
from datetime import datetime, timezone


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._snapshot: dict = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_snapshot(self, ws: WebSocket):
        """Send full state snapshot to a single client (on reconnect)."""
        if self._snapshot:
            await ws.send_json({
                "type": "snapshot",
                "data": self._snapshot,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def update_snapshot(self, data: dict):
        self._snapshot.update(data)
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_ws.py -v
```
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add admin/backend/ws.py tests/admin/test_ws.py
git commit -m "feat(admin): WebSocket ConnectionManager with broadcast and snapshot"
```

---

## Task 5: Poller (Background Polling + Delta Detection)

**Files:**
- Create: `admin/backend/poller.py`
- Test: `tests/admin/test_poller.py`

- [ ] **Step 1: Write failing test**

Create `tests/admin/test_poller.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from poller import Poller


@pytest.fixture
def mock_os_service():
    svc = MagicMock()
    svc.get_cluster_health.return_value = {"status": "green"}
    svc.get_node_stats.return_value = {"nodes": {}}
    svc.get_index_stats.return_value = []
    svc.get_active_ingestions.return_value = []
    return svc


@pytest.fixture
def mock_lr_service():
    svc = AsyncMock()
    svc.get_pipeline_status.return_value = {"busy": False}
    return svc


@pytest.fixture
def mock_ws():
    return AsyncMock()


def test_compute_diff_detects_change():
    poller = Poller.__new__(Poller)
    poller._last_snapshot = {"cluster_status": "green"}
    new = {"cluster_status": "yellow"}
    diff = poller._compute_diff(poller._last_snapshot, new)
    assert diff == {"cluster_status": "yellow"}


def test_compute_diff_no_change():
    poller = Poller.__new__(Poller)
    poller._last_snapshot = {"cluster_status": "green"}
    new = {"cluster_status": "green"}
    diff = poller._compute_diff(poller._last_snapshot, new)
    assert diff == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_poller.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement poller**

Create `admin/backend/poller.py`:
```python
import asyncio
import os
import json
from datetime import datetime, timezone
from services.opensearch import OpenSearchService
from services.lightrag import LightRAGService
from ws import ConnectionManager


class Poller:
    def __init__(
        self,
        os_service: OpenSearchService,
        lr_service: LightRAGService,
        ws_manager: ConnectionManager,
        log_dir: str = "./logs",
    ):
        self._os = os_service
        self._lr = lr_service
        self._ws = ws_manager
        self._log_dir = log_dir
        self._last_snapshot: dict = {}
        self._last_log_pos: int = 0
        self._last_log_file: str = ""
        self._running = False

    def _compute_diff(self, old: dict, new: dict) -> dict:
        return {k: v for k, v in new.items() if old.get(k) != v}

    async def _poll_system_health(self) -> dict:
        try:
            health = self._os.get_cluster_health()
            nodes = self._os.get_node_stats()
            indices = self._os.get_index_stats()
            overview = self._os.get_system_overview()
            knn = self._os.get_knn_stats()
            return {
                "system_health": {
                    "cluster": health,
                    "nodes": nodes,
                    "indices": indices,
                    "overview": overview,
                    "knn": knn,
                }
            }
        except Exception:
            return {"system_health": {"cluster": {"status": "disconnected"}}}

    async def _poll_ingestion(self) -> dict:
        try:
            active = self._os.get_active_ingestions()
            lr_status = await self._lr.get_pipeline_status()
            return {"ingestion": {"active": active, "pipeline": lr_status}}
        except Exception:
            return {}

    async def _poll_logs(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self._log_dir, f"rag-{today}.log")

        if log_file != self._last_log_file:
            self._last_log_file = log_file
            self._last_log_pos = 0

        if not os.path.exists(log_file):
            return []

        try:
            size = os.path.getsize(log_file)
            if size <= self._last_log_pos:
                return []

            entries = []
            with open(log_file, "r") as f:
                f.seek(self._last_log_pos)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            entries.append({"raw": line})
                self._last_log_pos = f.tell()
            return entries
        except Exception:
            return []

    async def poll_once(self):
        """Run one poll cycle. Used for testing and snapshot init."""
        data = {}
        health = await self._poll_system_health()
        data.update(health)
        ingestion = await self._poll_ingestion()
        data.update(ingestion)

        diff = self._compute_diff(self._last_snapshot, data)
        if diff:
            self._last_snapshot.update(data)
            self._ws.update_snapshot(self._last_snapshot)
            now = datetime.now(timezone.utc).isoformat()
            for key, value in diff.items():
                msg_type = "system_health" if key == "system_health" else "ingestion_update"
                await self._ws.broadcast({"type": msg_type, "data": value, "timestamp": now})

        log_entries = await self._poll_logs()
        if log_entries:
            now = datetime.now(timezone.utc).isoformat()
            for entry in log_entries:
                await self._ws.broadcast({"type": "log_entry", "data": entry, "timestamp": now})

    async def run(self):
        """Main polling loop with staggered intervals."""
        self._running = True
        tick = 0
        while self._running:
            await asyncio.sleep(1)
            tick += 1

            # Logs: every 2s
            if tick % 2 == 0:
                log_entries = await self._poll_logs()
                if log_entries:
                    now = datetime.now(timezone.utc).isoformat()
                    for entry in log_entries:
                        await self._ws.broadcast({"type": "log_entry", "data": entry, "timestamp": now})

            # Ingestion: every 5s
            if tick % 5 == 0:
                ingestion = await self._poll_ingestion()
                if ingestion:
                    diff = self._compute_diff(
                        {"ingestion": self._last_snapshot.get("ingestion")},
                        {"ingestion": ingestion.get("ingestion")},
                    )
                    if diff:
                        self._last_snapshot.update(ingestion)
                        self._ws.update_snapshot(self._last_snapshot)
                        now = datetime.now(timezone.utc).isoformat()
                        await self._ws.broadcast({"type": "ingestion_update", "data": ingestion["ingestion"], "timestamp": now})

            # System health: every 15s
            if tick % 15 == 0:
                health = await self._poll_system_health()
                if health:
                    diff = self._compute_diff(
                        {"system_health": self._last_snapshot.get("system_health")},
                        health,
                    )
                    if diff:
                        self._last_snapshot.update(health)
                        self._ws.update_snapshot(self._last_snapshot)
                        now = datetime.now(timezone.utc).isoformat()
                        await self._ws.broadcast({"type": "system_health", "data": health["system_health"], "timestamp": now})

    def stop(self):
        self._running = False
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_poller.py -v
```
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add admin/backend/poller.py tests/admin/test_poller.py
git commit -m "feat(admin): poller with delta detection, staggered intervals, and log tailing"
```

---

## Task 6: API Routers (System + Documents + Graph + Queries + Logs)

**Files:**
- Create: `admin/backend/routers/system.py`
- Create: `admin/backend/routers/documents.py`
- Create: `admin/backend/routers/graph.py`
- Create: `admin/backend/routers/queries.py`
- Create: `admin/backend/routers/logs.py`
- Test: `tests/admin/test_routers_system.py`
- Test: `tests/admin/test_routers_documents.py`
- Test: `tests/admin/test_routers_graph.py`
- Test: `tests/admin/test_routers_queries.py`
- Test: `tests/admin/test_routers_logs.py`

This task creates all 5 routers. Each router is thin — it delegates to the services and returns JSON.

- [ ] **Step 1: Write system router + test**

Create `admin/backend/routers/system.py`:
```python
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
```

Create `tests/admin/test_routers_system.py`:
```python
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.system import router


def _make_app():
    app = FastAPI()
    app.include_router(router)
    svc = MagicMock()
    svc.get_system_overview.return_value = {"cluster_status": "green", "documents": "10"}
    svc.get_cluster_health.return_value = {"status": "green"}
    svc.get_node_stats.return_value = {"nodes": {}}
    svc.get_knn_stats.return_value = {}
    app.state.os_service = svc
    return app


def test_get_health():
    client = TestClient(_make_app())
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overview"]["cluster_status"] == "green"
```

- [ ] **Step 2: Write documents router + test**

Create `admin/backend/routers/documents.py`:
```python
from fastapi import APIRouter, Request, UploadFile, File, Query

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


@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    lr_svc = request.app.state.lr_service
    content = await file.read()
    return await lr_svc.upload_document(content, file.filename)


@router.post("/scan")
async def scan_inbox(request: Request):
    lr_svc = request.app.state.lr_service
    return await lr_svc.scan_inbox()


@router.delete("/{doc_id}")
async def delete_document(request: Request, doc_id: str):
    lr_svc = request.app.state.lr_service
    return await lr_svc.delete_document(doc_id)


@router.post("/reprocess")
async def reprocess_failed(request: Request):
    lr_svc = request.app.state.lr_service
    return await lr_svc.reprocess_failed()
```

Create `tests/admin/test_routers_documents.py`:
```python
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.documents import router


def _make_app():
    app = FastAPI()
    app.include_router(router)
    os_svc = MagicMock()
    os_svc.get_ingestion_statuses.return_value = {"total": 1, "documents": [{"status": "ready"}]}
    os_svc.get_ingestion_analytics.return_value = {"status_counts": {"ready": 1}}
    lr_svc = AsyncMock()
    lr_svc.scan_inbox.return_value = {"status": "scanning_started"}
    lr_svc.reprocess_failed.return_value = {"status": "reprocessing_started"}
    app.state.os_service = os_svc
    app.state.lr_service = lr_svc
    return app


def test_list_documents():
    client = TestClient(_make_app())
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_analytics():
    client = TestClient(_make_app())
    resp = client.get("/api/documents/analytics")
    assert resp.status_code == 200


def test_scan_inbox():
    client = TestClient(_make_app())
    resp = client.post("/api/documents/scan")
    assert resp.status_code == 200
```

- [ ] **Step 3: Write graph router + test**

Create `admin/backend/routers/graph.py`:
```python
from fastapi import APIRouter, Request, Query

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
async def get_graph(
    request: Request,
    label: str = Query("*"),
    max_depth: int = Query(3, ge=1, le=10),
    max_nodes: int = Query(200, ge=1, le=2000),
):
    lr_svc = request.app.state.lr_service
    return await lr_svc.get_graph(label=label, max_depth=max_depth, max_nodes=max_nodes)


@router.get("/search")
async def search_labels(request: Request, q: str = Query(..., min_length=1), limit: int = Query(50)):
    lr_svc = request.app.state.lr_service
    return await lr_svc.search_labels(q, limit=limit)


@router.get("/popular")
async def popular_labels(request: Request, limit: int = Query(50)):
    lr_svc = request.app.state.lr_service
    return await lr_svc.get_popular_labels(limit=limit)
```

Create `tests/admin/test_routers_graph.py`:
```python
from unittest.mock import AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.graph import router


def _make_app():
    app = FastAPI()
    app.include_router(router)
    lr_svc = AsyncMock()
    lr_svc.get_graph.return_value = {"nodes": [], "edges": []}
    lr_svc.search_labels.return_value = ["Entity1"]
    lr_svc.get_popular_labels.return_value = ["Pop1"]
    app.state.lr_service = lr_svc
    return app


def test_get_graph():
    client = TestClient(_make_app())
    resp = client.get("/api/graph?label=*")
    assert resp.status_code == 200
    assert "nodes" in resp.json()


def test_search():
    client = TestClient(_make_app())
    resp = client.get("/api/graph/search?q=test")
    assert resp.status_code == 200


def test_popular():
    client = TestClient(_make_app())
    resp = client.get("/api/graph/popular")
    assert resp.status_code == 200
```

- [ ] **Step 4: Write queries router + test**

Create `admin/backend/routers/queries.py`:
```python
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
    params = {k: v for k, v in {
        "top_k": body.top_k, "chunk_top_k": body.chunk_top_k,
        "response_type": body.response_type, "enable_rerank": body.enable_rerank,
    }.items() if v is not None}
    result = await lr_svc.query(body.query, mode=body.mode, **params)
    elapsed_ms = int((time.time() - start) * 1000)

    # Save to query history
    try:
        os_svc.save_query_history({
            "query": body.query,
            "mode": body.mode,
            "response_time_ms": elapsed_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
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
```

Create `tests/admin/test_routers_queries.py`:
```python
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.queries import router


def _make_app():
    app = FastAPI()
    app.include_router(router)
    lr_svc = AsyncMock()
    lr_svc.query.return_value = {"response": "answer"}
    lr_svc.query_data.return_value = {"data": {}}
    os_svc = MagicMock()
    os_svc.save_query_history.return_value = None
    os_svc.get_query_history.return_value = []
    app.state.lr_service = lr_svc
    app.state.os_service = os_svc
    return app


def test_run_query():
    client = TestClient(_make_app())
    resp = client.post("/api/queries", json={"query": "test question"})
    assert resp.status_code == 200
    assert "response" in resp.json()
    assert "response_time_ms" in resp.json()


def test_get_history():
    client = TestClient(_make_app())
    resp = client.get("/api/queries/history")
    assert resp.status_code == 200
```

- [ ] **Step 5: Write logs router + test**

Create `admin/backend/routers/logs.py`:
```python
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
```

Create `tests/admin/test_routers_logs.py`:
```python
import os
import json
import tempfile
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.logs import router
from config import Settings


def _make_app(log_dir: str):
    app = FastAPI()
    app.include_router(router)
    app.state.settings = Settings(log_dir=log_dir)
    return app


def test_list_dates():
    with tempfile.TemporaryDirectory() as tmpdir:
        open(os.path.join(tmpdir, "rag-2026-03-23.log"), "w").close()
        open(os.path.join(tmpdir, "rag-2026-03-24.log"), "w").close()
        client = TestClient(_make_app(tmpdir))
        resp = client.get("/api/logs/dates")
        assert resp.status_code == 200
        dates = resp.json()
        assert "2026-03-24" in dates
        assert "2026-03-23" in dates


def test_get_logs():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "rag-2026-03-23.log")
        with open(log_path, "w") as f:
            f.write(json.dumps({"stage": "parsing", "status": "success"}) + "\n")
        client = TestClient(_make_app(tmpdir))
        resp = client.get("/api/logs/2026-03-23")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


def test_get_logs_missing_date():
    with tempfile.TemporaryDirectory() as tmpdir:
        client = TestClient(_make_app(tmpdir))
        resp = client.get("/api/logs/2099-01-01")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


def test_search_logs():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "rag-2026-03-23.log")
        with open(log_path, "w") as f:
            f.write(json.dumps({"stage": "parsing", "document": "AIA.pdf"}) + "\n")
            f.write(json.dumps({"stage": "metadata", "document": "FWD.pdf"}) + "\n")
        client = TestClient(_make_app(tmpdir))
        resp = client.get("/api/logs/2026-03-23/search?q=AIA")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
```

- [ ] **Step 6: Run all router tests**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/test_routers_*.py -v
```
Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add admin/backend/routers/ tests/admin/test_routers_*.py
git commit -m "feat(admin): all 5 API routers — system, documents, graph, queries, logs"
```

---

## Task 7: FastAPI App Assembly (main.py)

**Files:**
- Create: `admin/backend/main.py`

- [ ] **Step 1: Write main.py**

Create `admin/backend/main.py`:
```python
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from opensearchpy import OpenSearch

from config import load_settings
from ws import ConnectionManager
from poller import Poller
from services.opensearch import OpenSearchService
from services.lightrag import LightRAGService
from routers import system, documents, graph, queries, logs


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings

    # Init OpenSearch client
    os_client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        use_ssl=False,
    )
    os_service = OpenSearchService(os_client)
    app.state.os_service = os_service

    # Init LightRAG client
    lr_service = LightRAGService(settings.lightrag_api_url)
    app.state.lr_service = lr_service

    # Init WebSocket manager
    ws_manager = ConnectionManager()
    app.state.ws_manager = ws_manager

    # Init and start poller
    poller = Poller(os_service, lr_service, ws_manager, log_dir=settings.log_dir)
    app.state.poller = poller

    # Initial snapshot
    await poller.poll_once()

    # Start background polling
    task = asyncio.create_task(poller.run())

    yield

    # Shutdown
    poller.stop()
    task.cancel()
    await lr_service.close()


app = FastAPI(title="GEO Insurance RAG Admin", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(queries.router)
app.include_router(logs.router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    manager = app.state.ws_manager
    await manager.connect(ws)
    # Send initial snapshot
    await manager.send_snapshot(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "sync":
                await manager.send_snapshot(ws)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    settings = load_settings()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
```

- [ ] **Step 2: Smoke test — start the server**

```bash
cd admin/backend
PYTHONPATH=. OPENSEARCH_HOST=localhost OPENSEARCH_PORT=9200 LIGHTRAG_API_URL=http://localhost:9621 LOG_DIR=../../logs python main.py
```
Expected: Server starts on :8080. Hit `http://localhost:8080/api/system/health` — should return JSON (may error on LightRAG if not running, but OpenSearch data should come through).

- [ ] **Step 3: Commit**

```bash
git add admin/backend/main.py
git commit -m "feat(admin): FastAPI app with lifespan, WS endpoint, all routers mounted"
```

---

## Task 8: Frontend Setup + Layout + Nav

**Files:**
- Create: `admin/frontend/` (Next.js project)
- Create: `admin/frontend/src/app/layout.tsx`
- Create: `admin/frontend/src/app/globals.css`
- Create: `admin/frontend/src/components/nav.tsx`
- Create: `admin/frontend/src/hooks/use-dashboard-ws.ts`
- Create: `admin/frontend/src/hooks/use-api.ts`
- Create: `admin/frontend/src/lib/types.ts`

- [ ] **Step 1: Init Next.js project**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
pnpm create next-app admin/frontend --ts --tailwind --app --src-dir --no-eslint --import-alias "@/*"
```

- [ ] **Step 2: Install dependencies**

```bash
cd admin/frontend
pnpm add react-use-websocket@4 react-force-graph-2d @melloware/react-logviewer
pnpm add -D @types/node
```

- [ ] **Step 3: Init shadcn/ui**

```bash
cd admin/frontend
pnpm dlx shadcn@latest init
# Choose: Default style, Zinc color, CSS variables: yes
pnpm dlx shadcn@latest add button card table tabs badge input select separator scroll-area
```

- [ ] **Step 4: Write globals.css (dark theme)**

Replace `admin/frontend/src/app/globals.css`:
```css
@import "tailwindcss";

:root {
  --background: 0 0% 4%;
  --foreground: 0 0% 100%;
  --card: 0 0% 7%;
  --card-foreground: 0 0% 100%;
  --border: 0 0% 13%;
  --muted: 0 0% 10%;
  --muted-foreground: 0 0% 40%;
  --accent: 0 0% 10%;
  --accent-foreground: 0 0% 100%;
  --primary: 0 0% 100%;
  --primary-foreground: 0 0% 4%;
  --destructive: 0 84% 60%;
  --ring: 0 0% 20%;
  --radius: 0.5rem;
  --success: 142 71% 45%;
  --warning: 43 96% 56%;
  --error: 0 84% 60%;
}

body {
  background: hsl(var(--background));
  color: hsl(var(--foreground));
  font-family: system-ui, -apple-system, sans-serif;
}

.font-mono {
  font-family: 'SF Mono', Monaco, Consolas, 'Liberation Mono', monospace;
}
```

- [ ] **Step 5: Write types.ts**

Create `admin/frontend/src/lib/types.ts`:
```typescript
export interface SystemHealth {
  cluster: { status: string; number_of_nodes: number }
  nodes: Record<string, any>
  overview: {
    cluster_status: string
    documents: string
    entities: string
    relationships: string
    chunks: string
    llm_cache: string
    indices: any[]
  }
  knn: Record<string, any>
}

export interface IngestionStatus {
  active: Array<{
    document_id: string
    file_name: string
    status: string
    stages: Array<{ stage: string; status: string; duration_ms: number; error?: string }>
    metadata: Record<string, any>
  }>
  pipeline: { busy: boolean; docs?: number }
}

export interface WsMessage {
  type: 'system_health' | 'ingestion_update' | 'log_entry' | 'snapshot'
  data: any
  timestamp: string
}

export interface Document {
  document_id: string
  file_name: string
  status: string
  stages: Array<{ stage: string; status: string; duration_ms: number; error?: string }>
  metadata: {
    company?: string
    product_name?: string
    product_type?: string
    document_type?: string
    document_date?: string
    is_latest?: boolean
  }
  ingested_at?: string
}

export interface GraphData {
  nodes: Array<{ id: string; labels: string[]; properties: Record<string, any> }>
  edges: Array<{ id: string; source: string; target: string; type?: string; properties: Record<string, any> }>
}

export interface LogEntry {
  timestamp?: string
  document?: string
  stage?: string
  status?: string
  duration_ms?: number
  details?: Record<string, any>
  raw?: string
}
```

- [ ] **Step 6: Write use-api.ts hook**

Create `admin/frontend/src/hooks/use-api.ts`:
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

export async function api<T = any>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!resp.ok) throw new Error(`API error: ${resp.status}`)
  return resp.json()
}
```

- [ ] **Step 7: Write use-dashboard-ws.ts hook**

Create `admin/frontend/src/hooks/use-dashboard-ws.ts`:
```typescript
'use client'
import { useCallback, useEffect, useState } from 'react'
import useWebSocket from 'react-use-websocket'
import type { SystemHealth, IngestionStatus, LogEntry, WsMessage } from '@/lib/types'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8080/ws'

export function useDashboardWs() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null)
  const [ingestion, setIngestion] = useState<IngestionStatus | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])

  const { lastJsonMessage, readyState } = useWebSocket(WS_URL, {
    shouldReconnect: () => true,
    reconnectAttempts: Infinity,
    reconnectInterval: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
    onOpen: () => {
      // Request full snapshot on connect
    },
  })

  useEffect(() => {
    if (!lastJsonMessage) return
    const msg = lastJsonMessage as WsMessage

    switch (msg.type) {
      case 'system_health':
        setSystemHealth(msg.data)
        break
      case 'ingestion_update':
        setIngestion(msg.data)
        break
      case 'log_entry':
        setLogs(prev => [...prev.slice(-999), msg.data])
        break
      case 'snapshot':
        if (msg.data.system_health) setSystemHealth(msg.data.system_health)
        if (msg.data.ingestion) setIngestion(msg.data.ingestion)
        break
    }
  }, [lastJsonMessage])

  return { systemHealth, ingestion, logs, readyState }
}
```

- [ ] **Step 8: Write nav component**

Create `admin/frontend/src/components/nav.tsx`:
```tsx
'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const links = [
  { href: '/', label: 'Overview' },
  { href: '/documents', label: 'Documents' },
  { href: '/graph', label: 'Graph' },
  { href: '/queries', label: 'Queries' },
  { href: '/logs', label: 'Logs' },
]

export function Nav() {
  const pathname = usePathname()

  return (
    <header className="flex items-center justify-between border-b border-[hsl(var(--border))] px-6 py-3">
      <span className="text-sm font-semibold">GEO Insurance RAG</span>
      <nav className="flex gap-1">
        {links.map(({ href, label }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={`rounded px-3 py-1.5 text-xs transition-colors ${
                active
                  ? 'bg-[hsl(var(--muted))] text-white'
                  : 'text-[hsl(var(--muted-foreground))] hover:text-white'
              }`}
            >
              {label}
            </Link>
          )
        })}
      </nav>
    </header>
  )
}
```

- [ ] **Step 9: Write root layout**

Replace `admin/frontend/src/app/layout.tsx`:
```tsx
import type { Metadata } from 'next'
import { Nav } from '@/components/nav'
import './globals.css'

export const metadata: Metadata = {
  title: 'GEO Insurance RAG Admin',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[hsl(var(--background))]">
        <Nav />
        <main className="p-6">{children}</main>
      </body>
    </html>
  )
}
```

- [ ] **Step 10: Verify frontend starts**

```bash
cd admin/frontend && pnpm dev
```
Expected: Opens on localhost:3000, dark background, nav bar with 5 tabs visible.

- [ ] **Step 11: Commit**

```bash
git add admin/frontend/
git commit -m "feat(admin): Next.js frontend setup with dark theme, nav, WS hook, API wrapper"
```

---

## Task 9: Overview Page

**Files:**
- Create: `admin/frontend/src/components/stats-card.tsx`
- Create: `admin/frontend/src/components/system-health.tsx`
- Create: `admin/frontend/src/components/live-feed.tsx`
- Modify: `admin/frontend/src/app/page.tsx`

- [ ] **Step 1: Write stats-card component**

Create `admin/frontend/src/components/stats-card.tsx`:
```tsx
interface StatsCardProps {
  label: string
  value: string | number
  color?: string
}

export function StatsCard({ label, value, color }: StatsCardProps) {
  return (
    <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3">
      <div className="text-[9px] uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
        {label}
      </div>
      <div className={`font-mono text-2xl font-bold ${color || 'text-white'}`}>
        {value ?? '—'}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write system-health component**

Create `admin/frontend/src/components/system-health.tsx`:
```tsx
import type { SystemHealth } from '@/lib/types'

const statusColor: Record<string, string> = {
  green: 'text-[hsl(var(--success))]',
  yellow: 'text-[hsl(var(--warning))]',
  red: 'text-[hsl(var(--error))]',
  disconnected: 'text-[hsl(var(--error))]',
}

export function SystemHealthBar({ data }: { data: SystemHealth | null }) {
  if (!data) return <div className="text-xs text-[hsl(var(--muted-foreground))]">Loading...</div>

  const status = data.cluster?.status || 'disconnected'
  const firstNode = Object.values(data.nodes?.nodes || {})[0] as any
  const jvmPercent = firstNode?.jvm?.mem?.heap_used_percent ?? '—'
  const diskAvail = firstNode?.fs?.total?.available_in_bytes
  const diskTotal = firstNode?.fs?.total?.total_in_bytes
  const diskFree = diskAvail ? `${(diskAvail / 1e9).toFixed(0)}GB` : '—'

  return (
    <div className="flex items-center gap-6 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-4 py-2 font-mono text-xs">
      <span>
        <span className={statusColor[status]}>●</span> opensearch {status}
      </span>
      <span className="text-[hsl(var(--muted-foreground))]">│</span>
      <span>JVM: {jvmPercent}%</span>
      <span className="text-[hsl(var(--muted-foreground))]">│</span>
      <span>Disk: {diskFree} free</span>
    </div>
  )
}
```

- [ ] **Step 3: Write live-feed component**

Create `admin/frontend/src/components/live-feed.tsx`:
```tsx
import type { IngestionStatus } from '@/lib/types'

const statusIcon: Record<string, string> = {
  ready: '✓',
  failed: '✗',
  partial: '⚠',
}
const statusColor: Record<string, string> = {
  ready: 'text-[hsl(var(--success))]',
  failed: 'text-[hsl(var(--error))]',
  partial: 'text-[hsl(var(--warning))]',
  pending: 'text-[hsl(var(--warning))]',
  parsing: 'text-[hsl(var(--warning))]',
  validating: 'text-[hsl(var(--warning))]',
  extracting_metadata: 'text-[hsl(var(--warning))]',
  checking_version: 'text-[hsl(var(--warning))]',
  awaiting_confirmation: 'text-[hsl(var(--warning))]',
}

export function LiveFeed({ data }: { data: IngestionStatus | null }) {
  const items = data?.active || []

  return (
    <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
      <div className="mb-2 text-[9px] uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
        Live Ingestion
      </div>
      <div className="space-y-1 font-mono text-xs">
        {items.length === 0 && (
          <div className="text-[hsl(var(--muted-foreground))]">No active ingestions</div>
        )}
        {items.map((item) => (
          <div key={item.document_id} className="flex items-center gap-2">
            <span className={statusColor[item.status] || 'text-[hsl(var(--warning))]'}>
              {statusIcon[item.status] || '▶'}
            </span>
            <span className="flex-1 truncate">{item.file_name}</span>
            <span className={statusColor[item.status] || 'text-[hsl(var(--warning))]'}>
              {item.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Write overview page**

Replace `admin/frontend/src/app/page.tsx`:
```tsx
'use client'
import { StatsCard } from '@/components/stats-card'
import { SystemHealthBar } from '@/components/system-health'
import { LiveFeed } from '@/components/live-feed'
import { useDashboardWs } from '@/hooks/use-dashboard-ws'

export default function OverviewPage() {
  const { systemHealth, ingestion } = useDashboardWs()
  const o = systemHealth?.overview

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <StatsCard label="Documents" value={o?.documents ?? '—'} />
        <StatsCard label="Entities" value={o?.entities ?? '—'} />
        <StatsCard label="Relationships" value={o?.relationships ?? '—'} />
        <StatsCard label="Index Size" value={o?.index_size ?? '—'} />
      </div>
      <div className="grid grid-cols-4 gap-3">
        <StatsCard label="Chunks" value={o?.chunks ?? '—'} />
        <StatsCard label="Pending" value={o?.pending ?? '0'} color="text-[hsl(var(--warning))]" />
        <StatsCard label="Failed" value={o?.failed ?? '0'} color="text-[hsl(var(--error))]" />
        <StatsCard label="LLM Cache" value={o?.llm_cache ?? '—'} />
      </div>
      <SystemHealthBar data={systemHealth} />
      <LiveFeed data={ingestion} />
    </div>
  )
}
```

- [ ] **Step 5: Verify — open browser**

```bash
cd admin/frontend && pnpm dev
```
Open http://localhost:3000. Should see stat cards (showing "—" if backend not running), health bar, and live feed.

- [ ] **Step 6: Commit**

```bash
git add admin/frontend/src/
git commit -m "feat(admin): overview page with stat cards, system health, and live feed"
```

---

## Task 10: Documents Page

**Files:**
- Create: `admin/frontend/src/components/doc-table.tsx`
- Create: `admin/frontend/src/components/stage-timeline.tsx`
- Create: `admin/frontend/src/app/documents/page.tsx`

- [ ] **Step 1: Write doc-table + stage-timeline components**

Create `admin/frontend/src/components/stage-timeline.tsx`:
```tsx
interface Stage {
  stage: string
  status: string
  duration_ms: number
  error?: string
}

const stageOrder = ['validating', 'parsing', 'extracting_metadata', 'checking_version']

export function StageTimeline({ stages }: { stages: Stage[] }) {
  const stageMap = Object.fromEntries(stages.map((s) => [s.stage, s]))

  return (
    <div className="flex items-center gap-1 font-mono text-[10px]">
      {stageOrder.map((name) => {
        const s = stageMap[name]
        const color = !s
          ? 'bg-[hsl(var(--muted))]'
          : s.status === 'success' || s.status === 'no_match'
          ? 'bg-[hsl(var(--success))]'
          : s.status === 'failed'
          ? 'bg-[hsl(var(--error))]'
          : 'bg-[hsl(var(--warning))]'
        return (
          <div key={name} className="flex flex-col items-center gap-0.5" title={s ? `${s.duration_ms}ms` : 'pending'}>
            <div className={`h-1.5 w-8 rounded-full ${color}`} />
            <span className="text-[hsl(var(--muted-foreground))]">{name.slice(0, 4)}</span>
          </div>
        )
      })}
    </div>
  )
}
```

Create `admin/frontend/src/components/doc-table.tsx`:
```tsx
'use client'
import { useState, useEffect } from 'react'
import { api } from '@/hooks/use-api'
import { StageTimeline } from './stage-timeline'
import type { Document } from '@/lib/types'

const statusBadge: Record<string, string> = {
  ready: 'bg-[hsl(var(--success))]/20 text-[hsl(var(--success))]',
  failed: 'bg-[hsl(var(--error))]/20 text-[hsl(var(--error))]',
  partial: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
  pending: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
  awaiting_confirmation: 'bg-[hsl(var(--warning))]/20 text-[hsl(var(--warning))]',
}

export function DocTable() {
  const [docs, setDocs] = useState<Document[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('')

  useEffect(() => {
    const params = new URLSearchParams({ limit: '50', offset: '0' })
    if (statusFilter) params.set('status', statusFilter)
    api<{ total: number; documents: Document[] }>(`/api/documents?${params}`)
      .then((d) => { setDocs(d.documents); setTotal(d.total) })
      .catch(() => {})
  }, [statusFilter])

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <select
          className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-2 py-1 text-xs"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All ({total})</option>
          <option value="ready">Ready</option>
          <option value="failed">Failed</option>
          <option value="partial">Partial</option>
          <option value="pending">Pending</option>
          <option value="awaiting_confirmation">Awaiting Confirmation</option>
        </select>
      </div>
      <div className="overflow-x-auto rounded-md border border-[hsl(var(--border))]">
        <table className="w-full text-xs">
          <thead className="bg-[hsl(var(--muted))]">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">File</th>
              <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Status</th>
              <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Company</th>
              <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Product</th>
              <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Stages</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[hsl(var(--border))]">
            {docs.map((doc, i) => (
              <tr key={doc.document_id} className={i % 2 === 0 ? 'bg-[hsl(var(--card))]' : ''}>
                <td className="px-3 py-2 font-mono">{doc.file_name}</td>
                <td className="px-3 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] ${statusBadge[doc.status] || ''}`}>
                    {doc.status}
                  </span>
                </td>
                <td className="px-3 py-2">{doc.metadata?.company || '—'}</td>
                <td className="px-3 py-2">{doc.metadata?.product_name || '—'}</td>
                <td className="px-3 py-2"><StageTimeline stages={doc.stages || []} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write documents page**

Create `admin/frontend/src/app/documents/page.tsx`:
```tsx
import { DocTable } from '@/components/doc-table'

export default function DocumentsPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold">Documents</h2>
      <DocTable />
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add admin/frontend/src/
git commit -m "feat(admin): documents page with table, stage timeline, and status filter"
```

---

## Task 11: Graph Page

**Files:**
- Create: `admin/frontend/src/components/graph-viewer.tsx`
- Create: `admin/frontend/src/components/node-detail.tsx`
- Create: `admin/frontend/src/app/graph/page.tsx`

- [ ] **Step 1: Write graph-viewer component**

Create `admin/frontend/src/components/graph-viewer.tsx`:
```tsx
'use client'
import dynamic from 'next/dynamic'
import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/hooks/use-api'
import type { GraphData } from '@/lib/types'

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false })

const typeColors: Record<string, string> = {
  organization: '#4ade80',
  product: '#60a5fa',
  person: '#f472b6',
  coverage: '#fbbf24',
  default: '#94a3b8',
}

interface Props {
  onNodeClick: (node: any) => void
}

export function GraphViewer({ onNodeClick }: Props) {
  const [data, setData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] })
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<string[]>([])
  const graphRef = useRef<any>(null)

  useEffect(() => {
    api<GraphData>('/api/graph?label=*&max_nodes=200').then((g) => {
      setData({
        nodes: g.nodes.map((n) => ({
          id: n.id,
          label: n.id,
          type: n.properties?.entity_type || 'default',
          ...n.properties,
        })),
        links: g.edges.map((e) => ({
          source: e.source,
          target: e.target,
          type: e.type,
          weight: e.properties?.weight || 1,
        })),
      })
    }).catch(() => {})
  }, [])

  const handleSearch = useCallback(async (q: string) => {
    setSearch(q)
    if (q.length < 2) { setSearchResults([]); return }
    const results = await api<string[]>(`/api/graph/search?q=${encodeURIComponent(q)}`)
    setSearchResults(results)
  }, [])

  const focusNode = useCallback(async (label: string) => {
    const g = await api<GraphData>(`/api/graph?label=${encodeURIComponent(label)}&max_depth=2&max_nodes=100`)
    setData({
      nodes: g.nodes.map((n) => ({ id: n.id, label: n.id, type: n.properties?.entity_type || 'default', ...n.properties })),
      links: g.edges.map((e) => ({ source: e.source, target: e.target, type: e.type, weight: e.properties?.weight || 1 })),
    })
    setSearch('')
    setSearchResults([])
  }, [])

  return (
    <div className="flex flex-col gap-3">
      <div className="relative">
        <input
          type="text"
          placeholder="Search entities..."
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="w-full rounded border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-1.5 text-xs"
        />
        {searchResults.length > 0 && (
          <div className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
            {searchResults.map((r) => (
              <button key={r} onClick={() => focusNode(r)} className="block w-full px-3 py-1.5 text-left text-xs hover:bg-[hsl(var(--muted))]">
                {r}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))]" style={{ height: '500px' }}>
        <ForceGraph2D
          ref={graphRef}
          graphData={data}
          nodeLabel="label"
          nodeColor={(node: any) => typeColors[node.type] || typeColors.default}
          nodeRelSize={4}
          linkWidth={(link: any) => Math.max(0.5, (link.weight || 1) * 0.5)}
          linkColor={() => '#333'}
          onNodeClick={onNodeClick}
          backgroundColor="#111"
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write node-detail component**

Create `admin/frontend/src/components/node-detail.tsx`:
```tsx
interface Props {
  node: any | null
}

export function NodeDetail({ node }: Props) {
  if (!node) return (
    <div className="text-xs text-[hsl(var(--muted-foreground))]">Click a node to see details</div>
  )

  return (
    <div className="space-y-2 text-xs">
      <div className="font-semibold">{node.id || node.label}</div>
      <div className="space-y-1 font-mono">
        {node.type && <div><span className="text-[hsl(var(--muted-foreground))]">type:</span> {node.type}</div>}
        {node.description && <div><span className="text-[hsl(var(--muted-foreground))]">desc:</span> {node.description}</div>}
        {node.file_path && <div><span className="text-[hsl(var(--muted-foreground))]">file:</span> {node.file_path}</div>}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Write graph page**

Create `admin/frontend/src/app/graph/page.tsx`:
```tsx
'use client'
import { useState } from 'react'
import { GraphViewer } from '@/components/graph-viewer'
import { NodeDetail } from '@/components/node-detail'

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = useState<any>(null)

  return (
    <div className="flex gap-4">
      <div className="flex-1">
        <GraphViewer onNodeClick={setSelectedNode} />
      </div>
      <div className="w-72 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
        <div className="mb-2 text-[9px] uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
          Node Detail
        </div>
        <NodeDetail node={selectedNode} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add admin/frontend/src/
git commit -m "feat(admin): graph page with force-graph-2d, search, and node detail panel"
```

---

## Task 12: Queries Page

**Files:**
- Create: `admin/frontend/src/components/query-panel.tsx`
- Create: `admin/frontend/src/app/queries/page.tsx`

- [ ] **Step 1: Write query-panel component**

Create `admin/frontend/src/components/query-panel.tsx`:
```tsx
'use client'
import { useState } from 'react'
import { api } from '@/hooks/use-api'

const modes = ['hybrid', 'local', 'global', 'naive', 'mix', 'bypass']

export function QueryPanel() {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('hybrid')
  const [response, setResponse] = useState('')
  const [responseTime, setResponseTime] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!query.trim()) return
    setLoading(true)
    setResponse('')
    try {
      const result = await api<{ response: string; response_time_ms: number }>('/api/queries', {
        method: 'POST',
        body: JSON.stringify({ query, mode }),
      })
      setResponse(result.response)
      setResponseTime(result.response_time_ms)
    } catch (e: any) {
      setResponse(`Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Enter a query..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          className="flex-1 rounded border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-1.5 text-xs"
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-2 py-1 text-xs"
        >
          {modes.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="rounded bg-white px-3 py-1.5 text-xs font-medium text-black disabled:opacity-50"
        >
          {loading ? 'Querying...' : 'Query'}
        </button>
      </div>

      {response && (
        <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          {responseTime !== null && (
            <div className="mb-2 font-mono text-[10px] text-[hsl(var(--muted-foreground))]">
              {responseTime}ms · {mode}
            </div>
          )}
          <div className="whitespace-pre-wrap text-xs">{response}</div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Write queries page**

Create `admin/frontend/src/app/queries/page.tsx`:
```tsx
'use client'
import { useState, useEffect } from 'react'
import { QueryPanel } from '@/components/query-panel'
import { api } from '@/hooks/use-api'

export default function QueriesPage() {
  const [history, setHistory] = useState<any[]>([])

  useEffect(() => {
    api('/api/queries/history').then(setHistory).catch(() => {})
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-3 text-sm font-semibold">Query Test</h2>
        <QueryPanel />
      </div>
      <div>
        <h2 className="mb-3 text-sm font-semibold">History</h2>
        <div className="overflow-x-auto rounded-md border border-[hsl(var(--border))]">
          <table className="w-full text-xs">
            <thead className="bg-[hsl(var(--muted))]">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Query</th>
                <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Mode</th>
                <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Time</th>
                <th className="px-3 py-2 text-left font-medium text-[hsl(var(--muted-foreground))]">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {history.map((h, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-[hsl(var(--card))]' : ''}>
                  <td className="max-w-md truncate px-3 py-2 font-mono">{h.query}</td>
                  <td className="px-3 py-2 font-mono">{h.mode}</td>
                  <td className="px-3 py-2 font-mono">{h.response_time_ms}ms</td>
                  <td className="px-3 py-2 font-mono text-[hsl(var(--muted-foreground))]">{h.timestamp}</td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr><td colSpan={4} className="px-3 py-4 text-center text-[hsl(var(--muted-foreground))]">No queries yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add admin/frontend/src/
git commit -m "feat(admin): queries page with query test panel and history table"
```

---

## Task 13: Logs Page

**Files:**
- Create: `admin/frontend/src/components/log-viewer.tsx`
- Create: `admin/frontend/src/app/logs/page.tsx`

- [ ] **Step 1: Write log-viewer component**

Create `admin/frontend/src/components/log-viewer.tsx`:
```tsx
'use client'
import { useEffect, useRef } from 'react'
import type { LogEntry } from '@/lib/types'

function formatEntry(entry: LogEntry): string {
  if (entry.raw) return entry.raw
  const ts = entry.timestamp?.slice(11, 19) || ''
  const status = entry.status === 'success' ? '✓' : entry.status === 'failed' ? '✗' : '▶'
  return `${ts} ${status} ${entry.document || ''} · ${entry.stage || ''} · ${entry.duration_ms ?? 0}ms`
}

interface Props {
  entries: LogEntry[]
  filter: string
}

export function LogViewer({ entries, filter }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  const filtered = filter
    ? entries.filter((e) => JSON.stringify(e).toLowerCase().includes(filter.toLowerCase()))
    : entries

  return (
    <div className="h-[500px] overflow-y-auto rounded-md border border-[hsl(var(--border))] bg-black p-3 font-mono text-xs">
      {filtered.map((entry, i) => {
        const line = formatEntry(entry)
        const color = entry.status === 'failed' ? 'text-[hsl(var(--error))]'
          : entry.status === 'success' ? 'text-[hsl(var(--success))]'
          : 'text-[hsl(var(--muted-foreground))]'
        return (
          <div key={i} className={`leading-6 ${color}`}>
            {line}
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
```

- [ ] **Step 2: Write logs page**

Create `admin/frontend/src/app/logs/page.tsx`:
```tsx
'use client'
import { useState, useEffect } from 'react'
import { LogViewer } from '@/components/log-viewer'
import { api } from '@/hooks/use-api'
import { useDashboardWs } from '@/hooks/use-dashboard-ws'
import type { LogEntry } from '@/lib/types'

export default function LogsPage() {
  const [dates, setDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState('')
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [filter, setFilter] = useState('')
  const { logs: wsLogs } = useDashboardWs()

  useEffect(() => {
    api<string[]>('/api/logs/dates').then((d) => {
      setDates(d)
      if (d.length > 0) setSelectedDate(d[0])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedDate) return
    api<{ entries: LogEntry[] }>(`/api/logs/${selectedDate}`).then((d) => {
      setEntries(d.entries)
    }).catch(() => {})
  }, [selectedDate])

  // Append WebSocket log entries for today
  const today = new Date().toISOString().slice(0, 10)
  const allEntries = selectedDate === today ? [...entries, ...wsLogs] : entries

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold">Logs</h2>
        <select
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-2 py-1 text-xs"
        >
          {dates.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <input
          type="text"
          placeholder="Filter..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-2 py-1 text-xs"
        />
      </div>
      <LogViewer entries={allEntries} filter={filter} />
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add admin/frontend/src/
git commit -m "feat(admin): logs page with real-time log viewer, date selector, and filter"
```

---

## Task 14: Docker Compose Integration

**Files:**
- Modify: `docker/docker-compose.yml`
- Create: `admin/backend/Dockerfile`
- Create: `admin/frontend/Dockerfile`

- [ ] **Step 1: Write backend Dockerfile**

Create `admin/backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY . .
RUN pip install uv && uv pip install --system .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Write frontend Dockerfile**

Create `admin/frontend/Dockerfile`:
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV PORT=3000
CMD ["node", "server.js"]
```

**Important:** `next.config.ts` must include `output: 'standalone'` for the multi-stage Docker build to work. This is added in Task 8 Step 1.
```

- [ ] **Step 3: Update docker-compose.yml**

Update `docker/docker-compose.yml` to add the 3 new services (keep existing opensearch + dashboards, update their ports to 127.0.0.1):

```yaml
services:
  opensearch:
    image: opensearchproject/opensearch:3.0.0
    container_name: geo-rag-opensearch
    environment:
      - discovery.type=single-node
      - DISABLE_SECURITY_PLUGIN=true
      - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "127.0.0.1:9200:9200"
    volumes:
      - opensearch-data:/usr/share/opensearch/data

  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:3.0.0
    container_name: geo-rag-dashboards
    environment:
      - OPENSEARCH_HOSTS=["http://opensearch:9200"]
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    ports:
      - "127.0.0.1:5601:5601"
    depends_on:
      - opensearch

  lightrag-api:
    build: ..
    command: python -m lightrag.api.lightrag_server
    container_name: geo-rag-lightrag-api
    ports:
      - "127.0.0.1:9621:9621"
    env_file: ../.env
    environment:
      - OPENSEARCH_HOSTS=http://opensearch:9200
      - OPENSEARCH_USE_SSL=false
      - OPENSEARCH_VERIFY_CERTS=false
    depends_on:
      - opensearch

  admin-backend:
    build: ../admin/backend
    container_name: geo-rag-admin-backend
    ports:
      - "127.0.0.1:8080:8080"
    env_file: ../.env
    environment:
      - OPENSEARCH_HOST=opensearch
      - OPENSEARCH_PORT=9200
      - LIGHTRAG_API_URL=http://lightrag-api:9621
      - LOG_DIR=/logs
    volumes:
      - ../logs:/logs:ro
    depends_on:
      - opensearch
      - lightrag-api

  admin-frontend:
    build: ../admin/frontend
    container_name: geo-rag-admin-frontend
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8080
      - NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws
    depends_on:
      - admin-backend

volumes:
  opensearch-data:
```

- [ ] **Step 4: Commit**

```bash
git add docker/docker-compose.yml admin/backend/Dockerfile admin/frontend/Dockerfile
git commit -m "feat(admin): Docker Compose with LightRAG API, admin backend, and frontend services"
```

---

## Task 15: End-to-End Smoke Test

- [ ] **Step 1: Start OpenSearch (if not running)**

```bash
docker compose -f docker/docker-compose.yml up -d opensearch
```
Wait 30s for it to be healthy.

- [ ] **Step 2: Start admin backend (dev mode)**

```bash
cd admin/backend
PYTHONPATH=. OPENSEARCH_HOST=localhost OPENSEARCH_PORT=9200 LIGHTRAG_API_URL=http://localhost:9621 LOG_DIR=../../logs python main.py
```

- [ ] **Step 3: Start admin frontend (dev mode)**

```bash
cd admin/frontend
pnpm dev
```

- [ ] **Step 4: Verify each page**

Open http://localhost:3000 and check:
- Overview: stat cards load from OpenSearch, system health bar shows cluster status
- Documents: table shows documents from `rag-ingestion-status`
- Graph: force graph renders (may need LightRAG API running)
- Queries: query panel submits (may need LightRAG API running)
- Logs: date selector shows available dates, log entries render

- [ ] **Step 5: Run all backend tests**

```bash
PYTHONPATH=admin/backend python -m pytest tests/admin/ -v
```
Expected: all passed

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat(admin): complete V1 admin dashboard — overview, documents, graph, queries, logs"
```
