# MCP RAG Insurance System — Design Spec

## Overview

A Model Context Protocol (MCP) server that provides RAG (Retrieval-Augmented Generation) capabilities for querying Hong Kong insurance product documents. Insurance brokers connect via OpenClaw as the AI client gateway to ask questions about products from multiple insurance companies, without needing to manually review documents.

The system ingests PDF documents (product brochures, leaflets, training materials), extracts structured metadata via LLM, builds a knowledge graph, and exposes search/management tools through MCP.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    OpenClaw                          │
│              (AI Client Gateway)                     │
│         Users via WhatsApp/Telegram/Web              │
└──────────────────┬──────────────────────────────────┘
                   │ MCP (stdio / Streamable HTTP)
                   ▼
┌─────────────────────────────────────────────────────┐
│              MCP Server (Python)                     │
│         Thin wrapper exposing MCP tools              │
│                                                      │
│  Tools:                                              │
│  ├── query                 (semantic search + filter)│
│  ├── ingest_inbox          (process all inbox files) │
│  ├── ingest_document       (process single file)     │
│  ├── get_doc_status        (document pipeline status)│
│  ├── list_documents        (list indexed documents)  │
│  ├── delete_document       (remove from index)       │
│  ├── get_system_status     (system health)           │
│  └── confirm_version_update(confirm version replace) │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│   RAG-   │ │ Inbox    │ │   Logging    │
│ Anything │ │ Watcher  │ │  (file +     │
│ /LightRAG│ │(watchdog)│ │  OpenSearch) │
└────┬─────┘ └────┬─────┘ └──────────────┘
     │            │
     │     ┌──────▼──────┐
     │     │   MinerU    │
     │     │ (MLX GPU)   │
     │     │ PDF Parser  │
     │     └──────┬──────┘
     │            │
     │     ┌──────▼──────┐
     │     │  LLM Meta   │
     │     │  Extraction │
     │     │(gpt-4o-mini)│
     │     └──────┬──────┘
     │            │
     ▼            ▼
┌─────────────────────────────────────────────────────┐
│              OpenSearch 3.x (Docker)                 │
│                                                      │
│  ├── KV Store       (key-value storage)              │
│  ├── Vector Store   (embedding vector search)        │
│  ├── Graph Store    (knowledge graph entities/rels)  │
│  ├── DocStatus Store(document processing status)     │
│  └── Logs Index     (system logs)                    │
└─────────────────────────────────────────────────────┘
```

### External Services

- **YIBU API** (`https://yibuapi.com/v1`, fallback `https://yibu.pro/v1`) — LLM, embedding, vision model provider (OpenAI-compatible)
- **OpenClaw** — User-facing AI gateway (not managed by this system). Users set their own LLM in OpenClaw; this system only provides retrieved context via MCP tools.

---

## Technology Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| MCP Server | Python + FastMCP | Thin wrapper, stdio + Streamable HTTP |
| RAG Engine | RAG-Anything + LightRAG | Multimodal RAG with knowledge graph |
| PDF Parser | MinerU (MLX) | Mac ARM64 GPU accelerated, lang="ch" |
| Storage | OpenSearch 3.x | Unified via LightRAG native adapters: OpenSearchKVStorage, OpenSearchVectorDBStorage, OpenSearchGraphStorage, OpenSearchDocStatusStorage |
| Inbox Monitor | watchdog | Real-time file system monitoring |
| Package Manager | uv | Fast, modern Python package management |
| Embedding | text-embedding-3-large | Via YIBU API |
| LLM (internal) | gpt-4o-mini | Knowledge graph construction, metadata extraction |
| Vision Model | gpt-4o-mini | Table/image processing in PDFs |

---

## Deployment Topology

### Docker (docker-compose)
- OpenSearch 3.x (single node, k-NN plugin, port 9200, **persistent named volume for data**)
- OpenSearch Dashboards (port 5601)

### Local Python (uv)
- MCP Server + RAG-Anything + LightRAG
- MinerU (requires direct Mac GPU access via Metal/MLX)
- LightRAG WebUI (port 9621)

MinerU must run locally (not in Docker) to access Mac GPU.

---

## Project Structure

```
GEO-Insurance-RAG/
│
├── docker/
│   └── docker-compose.yml        # OpenSearch + Dashboards
│
├── src/
│   ├── server.py                 # MCP server entry point (FastMCP)
│   ├── rag.py                    # RAG-Anything / LightRAG init and wrapper
│   ├── ingestion.py              # Ingestion pipeline (parse → extract → index)
│   ├── metadata.py               # LLM metadata extraction logic
│   ├── versioning.py             # Version detection + confirmation logic
│   ├── watcher.py                # Inbox watchdog monitor
│   ├── logging_service.py        # Dual-write logging (file + OpenSearch)
│   └── config.py                 # Configuration management
│
├── data/
│   ├── inbox/                    # PDFs awaiting ingestion
│   ├── processed/                # Successfully ingested PDFs
│   └── failed/                   # Failed ingestion PDFs
│
├── logs/                         # Local log files
│
├── .env                          # Environment variables (git-ignored)
├── .env.example                  # Example environment variables (committed)
├── pyproject.toml                # uv dependency management
└── README.md
```

---

## Configuration (.env)

```env
# LLM (knowledge graph construction / query routing)
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-xxx
LLM_API_BASE=https://yibuapi.com/v1

# Embedding
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_API_BASE=https://yibuapi.com/v1

# Vision (image/table processing)
VISION_MODEL=gpt-4o-mini
VISION_API_KEY=sk-xxx
VISION_API_BASE=https://yibuapi.com/v1

# OpenSearch
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200

# MinerU
MINERU_DEVICE=mps
MINERU_LANG=ch
MINERU_PARSE_METHOD=auto

# Paths
INBOX_DIR=./data/inbox
PROCESSED_DIR=./data/processed
FAILED_DIR=./data/failed
LOG_DIR=./logs

# Limits
MAX_FILE_SIZE_MB=100
```

Each model has independent API key and base URL configuration, allowing different providers per model. This supports future migration (e.g., switching vision to MiniMax) without affecting other models.

---

## Document Metadata Schema

Extracted automatically by LLM (gpt-4o-mini) from document content during ingestion:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `company` | string | Insurance company name | AXA 安盛 |
| `product_name` | string | Product name | 智尊守慧醫療保障 |
| `product_type` | string | Product category | 醫療 / 儲蓄 / 人壽 / 意外 |
| `document_type` | string | Document category | 產品小冊子 / 宣傳單張 / 付款指引 / 培訓資料 |
| `document_date` | string | Document date/version | 2026-01 |
| `is_latest` | bool | Whether this is the latest version | true |

---

## Ingestion Pipeline

### Flow

```
PDF in inbox/ → Watchdog detects → Validate (PDF, ≤100MB)
  → MinerU parse (MLX GPU, lang="ch", parse_method="auto")
  → LLM extract metadata (gpt-4o-mini)
  → Version check (company + product_name match)
  → [If match found → awaiting_confirmation]
  → Index to OpenSearch
  → Move to processed/
```

### Document Status States

| State | Description |
|-------|-------------|
| `pending` | New file detected, queued |
| `validating` | Checking format and size (PDF, ≤100MB) |
| `parsing` | MinerU parsing in progress |
| `extracting_metadata` | LLM extracting metadata |
| `checking_version` | Checking for existing product versions |
| `awaiting_confirmation` | Possible version update detected, waiting for user |
| `indexing` | Writing to OpenSearch |
| `ready` | Complete, searchable |
| `partial` | Content indexed but metadata extraction failed |
| `failed` | Ingestion failed after 3 retries |

### Processing Rules

- **Sequential processing**: One file at a time to manage GPU memory and API rate limits
- **Retry policy**: 3 retries with exponential backoff (5s → 15s → 45s)
- **Partial ingestion**: If metadata extraction fails but content parsing succeeds, index with empty metadata (status: `partial`)
- **Validation failures**: Move immediately to `failed/` (no retry)
- **Duplicate detection**: SHA-256 file hash checked before processing; duplicate files are skipped and logged
- **Corrupt/encrypted PDFs**: If MinerU fails to open a PDF (corrupt or password-protected), move to `failed/` with descriptive error
- **File formats**: PDF only
- **File size**: Maximum 100MB
- **Language**: Only Traditional Chinese versions ingested; documents with mixed Chinese/English content are supported
- **Watchdog stabilization**: After detecting a new file, wait until file size is stable for 3 seconds before starting processing (prevents partial file reads during copy)

### Version Detection Logic

1. After metadata extraction, search existing documents by `company` + `product_name` + `document_type`
2. If no match: index directly with `is_latest: true`
3. If match found: set status to `awaiting_confirmation`, notify via MCP tool
4. User confirms via `confirm_version_update` tool:
   - `replace: true` → old document `is_latest: false`, new document `is_latest: true`
   - `replace: false` → new document indexed independently with `is_latest: true`
5. **Timeout**: Documents in `awaiting_confirmation` for more than 72 hours are automatically indexed as independent documents with `is_latest: true`

### Log Entry Format

```json
{
  "timestamp": "2026-03-22T14:30:00Z",
  "document": "AXA_WiseGuard_Pro_Brochure.pdf",
  "stage": "parsing",
  "status": "success",
  "duration_ms": 12500,
  "details": {
    "pages": 15,
    "tables_found": 3,
    "images_found": 8
  }
}
```

---

## Query System

### Query Flow

```
User question (via OpenClaw)
  → OpenClaw LLM calls MCP tool: query
  → LightRAG processes:
      1. Vector search (semantic similarity)
      2. Knowledge graph (entity relationships)
      3. Metadata filter (company, product_type, is_latest)
      4. Merge and rank results
  → Return structured JSON
  → OpenClaw LLM generates Chinese answer from context
```

### Supported Query Types

- **Product details**: "AXA 智尊守慧有冇等候期？"
- **Filtered search**: "AXA 有咩醫療保險產品？"
- **Cross-product comparison**: "比較 AXA 同 CTF Life 嘅儲蓄保險回報率"
- **Premium/return queries**: "薪火傳承 2 年繳嘅 IRR 係幾多？"
- **Promotion queries**: "而家有邊啲產品有保費折扣？"
- **Eligibility queries**: "55 歲可以買邊啲產品？"
- **Cross-type queries**: "有邊啲產品可以做保單逆按揭？"

### Response Language

All responses are in Chinese. The LLM in OpenClaw handles final answer generation; the MCP server returns retrieved context.

---

## MCP Tools — Error Response Schema

All MCP tools return a standard error envelope on failure:

```json
{
  "error": true,
  "error_code": "OPENSEARCH_UNAVAILABLE",
  "message": "OpenSearch is in degraded mode. Query and ingestion unavailable.",
  "details": {
    "last_connected": "2026-03-22T14:00:00Z",
    "retry_in_seconds": 5
  }
}
```

Error codes:
| Code | Description |
|------|-------------|
| `OPENSEARCH_UNAVAILABLE` | OpenSearch not connected |
| `API_UNAVAILABLE` | YIBU API unreachable (LLM/embedding/vision) |
| `VALIDATION_FAILED` | File validation failed (wrong format, too large) |
| `DOCUMENT_NOT_FOUND` | Document ID does not exist |
| `DUPLICATE_DOCUMENT` | File hash matches an already-ingested document |
| `INGESTION_FAILED` | Ingestion pipeline failed after retries |
| `INVALID_PARAMETERS` | Invalid tool parameters |

### API Outage Handling

When YIBU API is unavailable during ingestion:
- **During metadata extraction**: Content is indexed with empty metadata (status: `partial`). Can be re-processed later via `ingest_document` to fill metadata.
- **During knowledge graph construction**: Content is indexed as vector-only without graph relationships (status: `partial`). Re-ingestion rebuilds the graph.
- **During embedding**: Ingestion is paused and retried (3 attempts). If API remains down, document stays in `pending` and watcher retries on next cycle.

The `partial` status documents are fully queryable via vector search but may have degraded knowledge graph retrieval. Re-ingesting a `partial` document (same file hash) triggers re-processing instead of duplicate rejection. Re-processing skips version detection (document is already indexed) and only fills in missing metadata/graph data.

### Concurrency Rules

- **Query**: Concurrent calls allowed (OpenSearch handles concurrency)
- **Ingestion**: Concurrent `ingest_inbox`/`ingest_document` calls are queued; only one ingestion runs at a time
- **Document ID generation**: UUID v4, with a separate SHA-256 file hash stored for duplicate detection

---

## MCP Tools Interface

### 1. `query` — Search insurance product information

```
Parameters:
  question: string (required)     — User question
  filters: object (optional)      — Metadata filters
    company: string               — Insurance company name
    product_type: string          — 儲蓄/醫療/人壽/意外
    document_type: string         — 產品小冊子/宣傳單張/...
  mode: string (optional)         — auto|hybrid|local|global|naive|mix
                                    Default: auto
                                    Auto routing: hybrid for general questions,
                                    local for specific product lookups,
                                    global for cross-product comparisons
  top_k: int (optional)           — Number of results, default 5
  only_latest: bool (optional)    — Search latest versions only, default true

Returns:
  results: [{
    content: string               — Relevant content snippet
    source_document: string       — Source file name
    company: string               — Insurance company
    product_name: string          — Product name
    page: int                     — Page number
    relevance_score: float        — Relevance score
  }]
  metadata: {
    query_mode: string
    total_results: int
    filters_applied: object
    retrieval_time_ms: int
    documents_searched: int
    knowledge_graph_entities_matched: int
  }
```

### 2. `ingest_inbox` — Process all files in inbox

```
Parameters: (none)

Returns:
  queued: int                     — Files queued for processing
  skipped: int                    — Skipped files (non-PDF / over 100MB)
  files: [string]                 — Queued file names
```

### 3. `ingest_document` — Process a single document

```
Parameters:
  file_path: string (required)    — PDF file path

Returns:
  status: string                  — pending|validating|...
  document_id: string             — Document ID
```

### 4. `get_doc_status` — Query document processing status

```
Parameters:
  document_id: string (optional)  — Specific document ID
  file_name: string (optional)    — Specific file name
  status_filter: string (optional)— Filter by status
  limit: int (optional)           — Page size, default 20
  offset: int (optional)          — Pagination offset, default 0

Returns:
  documents: [{
    document_id: string
    file_name: string
    status: string
    stages: [{
      stage: string
      status: string
      duration_ms: int
      timestamp: string
      error: string|null
    }]
    metadata: object|null
  }]
  total: int
  limit: int
  offset: int
```

### 5. `list_documents` — List all indexed documents

```
Parameters:
  filters: object (optional)      — Same as query filters
  only_latest: bool (optional)    — Default true
  limit: int (optional)           — Page size, default 20
  offset: int (optional)          — Pagination offset, default 0

Returns:
  documents: [{
    document_id: string
    file_name: string
    company: string
    product_name: string
    product_type: string
    document_type: string
    document_date: string
    is_latest: bool
    ingested_at: string
    status: string
  }]
  total: int
  limit: int
  offset: int
```

### 6. `delete_document` — Delete a document from index

```
Parameters:
  document_id: string (required)
  confirm: bool (required)        — Must be true

Returns:
  success: bool
  message: string
  knowledge_graph_updated: bool   — If false, orphan graph nodes may remain;
                                    they are cleaned up on next ingestion cycle
```

### 7. `get_system_status` — System health status

```
Parameters: (none)

Returns:
  opensearch: {
    status: string                — healthy|degraded|disconnected
    documents_indexed: int
    index_size_mb: float
  }
  inbox: {
    pending_files: int
    watcher_active: bool
  }
  models: {
    llm: string
    embedding: string
    vision: string
    api_status: string            — healthy|degraded|unreachable
  }
```

### 8. `confirm_version_update` — Confirm version replacement

```
Parameters:
  document_id: string (required)  — Document in awaiting_confirmation state
  replace: bool (required)        — true=replace old / false=keep as independent

Returns:
  success: bool
  old_document_id: string|null
  message: string
```

---

## OpenSearch Health Check

On MCP server startup:
1. Attempt connection to OpenSearch every 5 seconds, up to 60 seconds
2. If connected within 60s: normal startup
3. If not connected after 60s: start in **degraded mode**
   - Query and ingestion tools return clear error messages
   - Background thread continues retry attempts
   - Server does not crash

---

## Logging Strategy

Dual-write logging:
- **Local log files** (`./logs/`): Immediate access, fallback if OpenSearch is down
- **OpenSearch logs index**: Queryable via Dashboards, supports visualization (ingestion success rates, processing time trends)

Both destinations receive identical structured JSON log entries covering every pipeline stage.

---

## UI / Debug Tools

| Tool | Port | Purpose |
|------|------|---------|
| LightRAG WebUI | 9621 | Knowledge graph visualization, test queries, document management |
| OpenSearch Dashboards | 5601 | Index data inspection, query debugging, health monitoring, log visualization |

Both are admin/debug tools, not user-facing. Brokers interact through OpenClaw.

---

## OpenSearch Integration Details

LightRAG provides native OpenSearch storage adapters (added March 2026). No custom adapters needed:

| LightRAG Storage | OpenSearch Adapter | Purpose |
|------------------|--------------------|---------|
| KV Store | `OpenSearchKVStorage` | Key-value pairs for document chunks |
| Vector Store | `OpenSearchVectorDBStorage` | Embedding vectors with k-NN search |
| Graph Store | `OpenSearchGraphStorage` | Knowledge graph nodes and edges as documents |
| Doc Status | `OpenSearchDocStatusStorage` | Document processing state tracking |

Additionally, the system creates a `rag-logs` index for dual-write logging.

Requires: OpenSearch 3.x with k-NN plugin enabled.

---

## Future Considerations (Not In Scope)

- **MiniMax compatibility**: Achievable by changing model config (API key + base URL) per model
- **Automated document download skills**: Future skill places PDFs in `inbox/` folder
- **Custom admin frontend**: Can be built on top of MCP status APIs
- **Knowledge graph domain hints**: Insurance-specific entity extraction prompts (optimize later)
- **Authentication**: Add API key auth for Streamable HTTP when needed
- **Multi-tenant / scaling**: Not needed for current user base
