# Admin Dashboard Design Spec

## Overview

GEO Insurance RAG 嘅 admin dashboard，俾 solo admin 用嚟 monitor 系統狀態、管理文件、探索知識圖譜、測試 RAG query、同查看 logs。Dark minimal UI + monospace data style，real-time WebSocket updates。

## Prerequisites

Before building the dashboard, apply these fixes to the existing system:
1. Set `rag-ingestion-status` index replicas to 0 (currently 1, causes yellow status on single-node)
2. Update existing docker-compose.yml to bind OpenSearch ports to 127.0.0.1 (`"127.0.0.1:9200:9200"`, `"127.0.0.1:5601:5601"`)
3. Add `.superpowers/` to `.gitignore` if not already present

## Decisions

| Item | Decision | Rationale |
|------|----------|-----------|
| User | Solo admin, no auth | 只有自己用 |
| Architecture | Monorepo, independent web app | Code reuse + deployment simplicity |
| Frontend | Next.js 16 App Router | SSR, file-based routing, React 19 |
| Backend | FastAPI (Python) | 直接用 opensearch-py, 同現有 stack 一致 |
| Real-time | WebSocket (not SSE) | 雙向通訊, 未來 upgrade path 好 |
| Graph data | LightRAG API as backend | 避免 reinvent BFS/traversal/CRUD |
| Data source | OpenSearch as source of truth | Dashboard reads OpenSearch directly; MCP server in-memory state may differ due to best-effort persistence |
| Ingestion ops | Dual coordination | LightRAG API handles RAG indexing; admin backend manages rag-ingestion-status tracking |
| UI style | F3 — Dark minimal shell + monospace data | F1 大數字 stats on overview |

## Architecture

```
GEO-Insurance-RAG/
├── src/                          # 現有 MCP server（唔改動）
├── admin/
│   ├── backend/                  # FastAPI — thin proxy + aggregator
│   │   ├── main.py               # FastAPI app, CORS, lifespan, WS
│   │   ├── ws.py                 # WebSocket ConnectionManager
│   │   ├── poller.py             # Poll OpenSearch → broadcast changes via WS
│   │   ├── routers/
│   │   │   ├── system.py         # OpenSearch cluster/node/knn stats
│   │   │   ├── documents.py      # Proxy → LightRAG /documents/* + rag-ingestion-status
│   │   │   ├── graph.py          # Proxy → LightRAG /graph/* + /graphs
│   │   │   ├── queries.py        # Proxy → LightRAG /query/* + query history
│   │   │   └── logs.py           # Read log files + stream via WS
│   │   └── services/
│   │       ├── opensearch.py     # Direct OpenSearch client (cluster stats, index info)
│   │       └── lightrag.py       # httpx async client → LightRAG API
│   │
│   └── frontend/                 # Next.js 16 App Router
│       ├── src/app/
│       │   ├── layout.tsx        # Dark theme, sidebar nav, WS provider
│       │   ├── page.tsx          # Overview dashboard
│       │   ├── documents/page.tsx
│       │   ├── graph/page.tsx
│       │   ├── queries/page.tsx
│       │   └── logs/page.tsx
│       ├── components/
│       │   ├── ui/               # shadcn/ui components
│       │   ├── stats-card.tsx
│       │   ├── live-feed.tsx
│       │   ├── graph-viewer.tsx
│       │   └── log-viewer.tsx
│       └── lib/
│           └── api-client/       # @hey-api/openapi-ts generated
```

### Data Flow

```
Frontend :3000
   │
   ├─ REST ──→ Admin Backend :8080
   │              ├─ /api/system/*    → OpenSearch :9200 直接 query
   │              ├─ /api/documents/* → LightRAG :9621 proxy + OpenSearch enrichment
   │              ├─ /api/graph/*     → LightRAG :9621 proxy
   │              ├─ /api/queries/*   → LightRAG :9621 proxy
   │              └─ /api/logs/*      → Read log files
   │
   └─ WebSocket → Admin Backend :8080/ws
                    └─ poller.py (variable intervals)
                       ├─ Poll OpenSearch cluster health (15s)
                       ├─ Poll rag-ingestion-status changes (5s)
                       ├─ Poll LightRAG /documents/status (5s)
                       ├─ Poll index stats (30s)
                       └─ Tail log file changes (2s)
                       → Broadcast deltas to all connected clients
```

### Port Allocation

| Service | Port | Exposure |
|---------|------|----------|
| OpenSearch | 9200 | 127.0.0.1 only |
| OpenSearch Dashboards | 5601 | 127.0.0.1 only |
| LightRAG API | 9621 | 127.0.0.1 (accessible from host for debugging, primarily used via admin backend proxy) |
| Admin Backend | 8080 | localhost |
| Admin Frontend | 3000 | localhost |

## Page Designs

### Overview Page (`/`)

**Layout:** F3 minimal shell + F1 large stat numbers

**Components:**
- 8 stat cards (Documents, Entities, Relations, Index Size, Chunks, Pending, Failed, LLM Cache)
  - Data: OpenSearch `_cat/indices?format=json` + `_count` per index
  - "LLM Cache" = `llm_response_cache` index doc count
- System health bar (OpenSearch status, LLM/embedding/vision connectivity, JVM heap, disk, k-NN cache)
  - Data: `_cluster/health` + `_nodes/stats/jvm,fs,os` + `_plugins/_knn/stats`
- Live ingestion feed (monospace, terminal-style, progress bars)
  - Data: `rag-ingestion-status` where status != ready, via WebSocket push

### Documents Page (`/documents`)

**Components:**
- Document table (sortable, filterable by status/company/product_type/document_type)
  - Data: `rag-ingestion-status` index with pagination
- Ingestion stage timeline per document (pending → validating → parsing → extracting_metadata → checking_version → awaiting_confirmation → ready/partial/failed)
  - Data: `rag-ingestion-status.stages` nested field, includes duration_ms per stage
  - `partial` state shown with warning badge (indexed but metadata extraction failed)
  - `awaiting_confirmation` shows confirm/reject buttons
- Actions:
  - Upload PDF → LightRAG `POST /documents/upload` + admin backend creates `rag-ingestion-status` record
  - Scan inbox → LightRAG `POST /documents/scan`
  - Delete document → LightRAG `DELETE /documents/{doc_id}` + admin backend deletes `rag-ingestion-status` record
  - Reprocess failed → LightRAG `POST /documents/reprocess_failed`
  - Confirm version update → Admin backend updates `rag-ingestion-status` (status + is_latest)
- Metadata viewer panel (company, product_name, product_type, document_type, document_date, is_latest)
- Ingestion analytics:
  - Average processing time per stage (bar chart)
  - Success rate over time (line chart)
  - Failure breakdown by stage (pie chart)
  - Data: Aggregation queries on `rag-ingestion-status.stages`

### Graph Page (`/graph`)

**Components:**
- Interactive force graph (react-force-graph-2d, `'use client'` + `dynamic` import + `ssr: false`)
  - Data: LightRAG `GET /graphs?label=*&max_nodes=200` (default 200, "load more" button to expand)
  - Nodes color-coded by entity_type
  - Edge thickness by weight
- Search bar with fuzzy matching
  - Data: LightRAG `GET /graph/label/search?q=`
- Popular entities sidebar (top N by degree)
  - Data: LightRAG `GET /graph/label/popular?limit=50`
- Node detail panel (click node → show type, description, connections)
  - Data: LightRAG `GET /graphs?label=X&max_depth=1`
- Entity CRUD (create, edit, delete)
  - Data: LightRAG `POST /graph/entity/create|edit`, `DELETE /graph/entity`
- Relationship CRUD (create, edit, delete)
  - Data: LightRAG `POST /graph/relation/create|edit`, `DELETE /graph/relation`
- Merge duplicates
  - Data: LightRAG `POST /graph/entities/merge`

### Queries Page (`/queries`)

**Components:**
- Query test panel:
  - Input box + mode selector (local/global/hybrid/naive/mix/bypass)
  - Param controls: top_k, chunk_top_k, response_type, enable_rerank
  - Streaming response display
  - Data: LightRAG `POST /query/stream`
- Structured data view (returned entities + relations + chunks in table)
  - Data: LightRAG `POST /query/data`
- Mode comparison (run same query across multiple modes side-by-side)
  - Frontend parallel calls
- Query history table with response time
  - Data: Admin backend logs to new `rag-query-history` OpenSearch index
  - Note: Only captures dashboard test queries, not MCP server queries (no changes to src/)

### Logs Page (`/logs`)

**Components:**
- Real-time log stream (monospace, @melloware/react-logviewer)
  - Data: Backend tails `logs/rag-YYYY-MM-DD.log` → pushes via WebSocket
- Filter by stage / status / document name
  - Frontend-side filter on incoming WS messages
- Search within logs
  - Backend reads log file + grep
- Date selector (pick which day's log to view)
  - Backend lists `logs/` directory

## WebSocket Protocol

### Connection
```
ws://localhost:8080/ws
```

### Server → Client Messages
```json
{
  "type": "ingestion_update | system_health | log_entry | document_change",
  "data": { ... },
  "timestamp": "2026-03-23T12:34:56Z"
}
```

### Client → Server Messages
```json
{
  "type": "sync"
}
```
Sent on reconnect. Server responds with full state snapshot.

### Polling Strategy

| Data | Interval | Source | WS Message Type |
|------|----------|--------|-----------------|
| Cluster health + JVM/disk | 15s | `_cluster/health` + `_nodes/stats` | `system_health` |
| Ingestion status changes | 5s | `rag-ingestion-status` query | `ingestion_update` |
| LightRAG pipeline status | 5s | `GET /documents/status` | `ingestion_update` |
| Index stats (doc count, size) | 30s | `_cat/indices?format=json` | `system_health` |
| k-NN stats | 30s | `_plugins/_knn/stats` | `system_health` |
| Log file tail | 2s | `os.stat()` mtime check + read new lines | `log_entry` |

### Delta Broadcasting

Poller caches last snapshot. Only broadcasts when data changes. On client reconnect (sync message), sends full snapshot.

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Frontend** | | |
| Framework | Next.js (App Router) | 16.x |
| UI Components | shadcn/ui (copy-paste) | latest |
| Charts | shadcn/ui charts (Recharts wrapper) | latest |
| Graph Viz | react-force-graph-2d | 1.29 |
| WebSocket | react-use-websocket | 4.13 |
| Log Viewer | @melloware/react-logviewer | 6.4 |
| API Client | @hey-api/openapi-ts | 0.94 |
| Styling | Tailwind CSS v4 | latest |
| **Backend** | | |
| Framework | FastAPI | 0.135 |
| OpenSearch Client | opensearch-py | 3.1 |
| HTTP Client | httpx | latest |
| **Infrastructure** | | |
| LightRAG API | LightRAG built-in server (`lightrag.api.lightrag_server`) | :9621 |
| OpenSearch | opensearch | 3.0 |
| Container | Docker Compose | — |
| **Dev** | | |
| Python pkg manager | uv | latest |
| JS pkg manager | pnpm | latest |

## Docker Compose Additions

```yaml
lightrag-api:
  build: .
  command: python -m lightrag.api.lightrag_server
  ports: ["127.0.0.1:9621:9621"]
  env_file: ../.env
  environment:
    - OPENSEARCH_HOSTS=http://opensearch:9200
    - OPENSEARCH_USE_SSL=false
    - OPENSEARCH_VERIFY_CERTS=false
  depends_on: [opensearch]

admin-backend:
  build: ./admin/backend
  ports: ["127.0.0.1:8080:8080"]
  env_file: ../.env
  environment:
    - OPENSEARCH_HOST=opensearch
    - OPENSEARCH_PORT=9200
    - LIGHTRAG_API_URL=http://lightrag-api:9621
  depends_on: [opensearch, lightrag-api]

admin-frontend:
  build: ./admin/frontend
  ports: ["127.0.0.1:3000:3000"]
  environment:
    - NEXT_PUBLIC_API_URL=http://localhost:8080
    - NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws
  depends_on: [admin-backend]
```

## OpenSearch Indices Reference

### Existing Indices (19 total, verified)

**LightRAG KV Storage:**
- `full_docs` (2 docs) — Full document content
- `text_chunks` (147 docs) — Text chunk metadata
- `llm_response_cache` (303 docs) — LLM extraction cache
- `full_entities` (2 docs) — Per-document entity lists
- `full_relations` (2 docs) — Per-document relation lists
- `entity_chunks` (0 docs) — Entity-chunk associations
- `relation_chunks` (0 docs) — Relation-chunk associations
- `parse_cache` (2 docs) — MinerU parse results cache

**LightRAG Vector Storage (3072-dim HNSW cosine):**
- `entities` (865 docs, 10.8 MB) — Entity embeddings
- `relationships` (1,725 docs, 41.6 MB) — Relationship embeddings
- `chunks` (147 docs, 1.9 MB) — Chunk embeddings

**LightRAG Graph Storage:**
- `chunk_entity_relation-nodes` (865 docs) — Entity nodes (entity_id, entity_type, description, source_ids, file_path)
- `chunk_entity_relation-edges` (1,725 docs) — Relationship edges (source_node_id, target_node_id, relationship, weight, keywords, description)

**LightRAG Doc Status:**
- `doc_status` (2 docs) — LightRAG internal document tracking

**Custom (our code):**
- `rag-ingestion-status` (18 docs) — Pipeline stage tracking with nested stages array + metadata

### New Index (to be created)
- `rag-query-history` — Query test history (query text, mode, response time, timestamp)

### Note
- `rag-logs` index does NOT exist currently (logger writes fail silently). Log viewer uses file-based logs as primary source.
- `rag-ingestion-status` is yellow (1 replica on single-node). Should set replicas to 0.

## UI Style

- **Theme:** Dark (#0a0a0a background, #111 cards, #222 borders)
- **Typography:** System font for UI chrome (nav, labels, headings), monospace (SF Mono/Consolas) for all data values
- **Stats cards:** Large monospace numbers (F1 style) on overview, compact inline (F3 style) on other pages
- **Live feed:** Terminal-style with status icons (▶ ✓ ✗), progress bars (████░░), monospace
- **Tab nav:** Pill-style tabs in top bar (Overview, Documents, Graph, Queries, Logs)
- **Tables:** Zebra striping on dark background, monospace data cells
- **Color palette:**
  - Green (#4ade80) — healthy, ready, success
  - Yellow (#fbbf24) — pending, parsing, warning
  - Red (#f87171) — failed, error
  - Gray (#666) — labels, secondary text
  - White (#fff) — primary text, stat numbers

## Error Handling

- OpenSearch unavailable → System health shows "disconnected", stats cards show "—"
- LightRAG API unavailable → Graph/query/document pages show error banner, overview stats still work (from OpenSearch directly)
- WebSocket disconnected → Frontend shows reconnecting indicator, auto-reconnect with exponential backoff
- Log file missing → Log viewer shows "No logs for selected date"

## Data Ownership

The dashboard interacts with two separate document tracking systems:

1. **`rag-ingestion-status`** (our custom index) — Tracks pipeline stages, metadata extraction, version management. Written by admin backend.
2. **LightRAG `doc_status`** (LightRAG internal) — Tracks RAG indexing (chunking, embedding, graph extraction). Written by LightRAG API.

When admin triggers document upload:
1. Admin backend creates `rag-ingestion-status` record (status: pending)
2. Admin backend calls LightRAG `POST /documents/upload`
3. Admin backend polls LightRAG `GET /documents/status` for progress
4. On LightRAG completion, admin backend updates `rag-ingestion-status` (status: ready)
5. Admin backend runs metadata extraction (calls LLM) and updates metadata fields

Note: The MCP server (`src/server.py`) has its own in-memory `IngestionPipeline` with `_doc_statuses` dict. This may diverge from OpenSearch due to best-effort persistence. The dashboard treats OpenSearch as the source of truth and does not interact with the MCP server process.

## Security Notes

- OpenSearch has DISABLE_SECURITY_PLUGIN=true — all ports bound to 127.0.0.1
- No auth on admin dashboard (solo admin, local only)
- Admin backend is read-heavy; write operations limited to document management + graph CRUD
- Config displayed as read-only (no runtime config changes via UI)

## Scope Notes (V1 vs V2)

**V1 (initial build):**
- All pages: Overview, Documents, Graph (read-only), Queries, Logs
- Graph entity/relationship CRUD deferred to V2
- Mode comparison deferred to V2
- OpenAPI client generation optional (can use simple fetch wrapper)

**V2 (future):**
- Graph CRUD (create, edit, delete, merge entities/relationships)
- Query mode comparison (side-by-side)
- Server-side log filtering via WS subscription
- MCP server query logging to `rag-query-history`
