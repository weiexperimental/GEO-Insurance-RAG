# GEO Insurance RAG

An MCP (Model Context Protocol) server with a full-stack admin dashboard, purpose-built for Hong Kong insurance brokers. Brokers connect through [OpenClaw](https://github.com/nicepkg/openclaw) (an AI gateway) and query insurance product information using natural language — no manual document review required.

The system ingests PDF documents (product brochures, leaflets, pricing guides), parses them with OCR, builds a knowledge graph, and exposes semantic search + graph-augmented retrieval through MCP tools.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Directory Structure](#directory-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Services](#running-the-services)
- [MCP Tools](#mcp-tools)
- [Admin Dashboard](#admin-dashboard)
- [OpenClaw Integration](#openclaw-integration)
- [Document Ingestion Pipeline](#document-ingestion-pipeline)
- [RAG Engine](#rag-engine)
- [Knowledge Graph](#knowledge-graph)
- [Evaluation System](#evaluation-system)
- [Deployment](#deployment)
- [Testing](#testing)
- [Design Decisions](#design-decisions)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenClaw Gateway                         │
│                    (AI Agent + Chat Interface)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ MCP (stdio / Streamable HTTP)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (FastMCP)                         │
│                                                                 │
│  Tools: query · ingest · ingest_all · list_documents ·          │
│         delete_document · get_system_status                     │
│                                                                 │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  RAG Engine   │  │ Ingestion Service│  │ Metadata Extractor│  │
│  │ (RAGAnything  │  │ (MinerU PDF      │  │ (LLM-based field │  │
│  │  + LightRAG)  │  │  parser + retry) │  │  extraction)     │  │
│  └──────┬───────┘  └────────┬─────────┘  └──────────────────┘  │
│         │                   │                                   │
└─────────┼───────────────────┼───────────────────────────────────┘
          │                   │
          ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OpenSearch 3.x                               │
│                                                                 │
│  Indices: text_chunks · entities · chunk_entity_relation-nodes  │
│           chunk_entity_relation-edges · doc_status · rag-logs   │
│           llm_response_cache · eval_qa_pairs · eval_runs        │
└─────────────────────────────────────────────────────────────────┘
          ▲
          │
┌─────────┴───────────────────────────────────────────────────────┐
│                     Admin Dashboard                              │
│                                                                 │
│  Backend: FastAPI (port 8080)    Frontend: Next.js (port 3000)  │
│  WebSocket real-time updates     React 19 + Tailwind CSS 4      │
│  Caddy reverse proxy (port 80)                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **MCP Server** | [FastMCP 3.x](https://github.com/jlowin/fastmcp) | MCP protocol framework — exposes tools to AI agents |
| **RAG Engine** | [RAG-Anything](https://github.com/RagAnything/RagAnything) + [LightRAG](https://github.com/HKUDS/LightRAG) | Multimodal RAG with knowledge graph augmented retrieval |
| **PDF Parser** | [MinerU](https://github.com/opendatalab/MinerU) (MLX GPU) | PDF-to-Markdown conversion with OCR — Metal accelerated on Apple Silicon |
| **Storage** | [OpenSearch 3.x](https://opensearch.org/) | Unified storage for vectors, graph data, key-value pairs, and document status |
| **LLM/Embedding/Vision** | YIBU API (OpenAI-compatible) | `gpt-4o-mini` for LLM + vision, `text-embedding-3-large` (3072-dim) for embeddings |
| **Admin Backend** | [FastAPI](https://fastapi.tiangolo.com/) | REST API + WebSocket for admin dashboard |
| **Admin Frontend** | [Next.js 16](https://nextjs.org/) + React 19 | Admin UI with real-time updates |
| **Reverse Proxy** | [Caddy 2](https://caddyserver.com/) | Routes `/api/*` and `/ws` to backend, everything else to frontend |
| **Language** | Python 3.12 | Required — MinerU does not support Python 3.14 |

---

## Directory Structure

```
GEO-Insurance-RAG/
├── src/                          # Core MCP server
│   ├── server.py                 # MCP entry point — 6 tools
│   ├── config.py                 # Environment config loader (dataclasses)
│   ├── rag.py                    # RAGAnything + LightRAG wrapper
│   ├── ingestion.py              # PDF ingestion pipeline (retry, dedup, metadata)
│   ├── metadata.py               # LLM-based metadata extraction
│   └── logging_service.py        # Structured JSON logging + OpenSearch indexing
│
├── admin/                        # Admin dashboard (full-stack)
│   ├── backend/                  # FastAPI backend
│   │   ├── main.py               # App entry — lifespan, CORS, routers, WebSocket
│   │   ├── config.py             # Admin-specific settings
│   │   ├── poller.py             # Background polling (health, ingestion, logs)
│   │   ├── ws.py                 # WebSocket connection manager
│   │   ├── Dockerfile
│   │   ├── routers/              # API route handlers
│   │   │   ├── system.py         # GET /api/system/health
│   │   │   ├── documents.py      # CRUD /api/documents/*
│   │   │   ├── graph.py          # /api/graph/* (nodes, edges, search, merge)
│   │   │   ├── chunks.py         # /api/chunks/* (quality, edit, delete)
│   │   │   ├── query_playground.py  # /api/playground/* (query testing)
│   │   │   ├── eval.py           # /api/eval/* (QA pairs, runs)
│   │   │   └── logs.py           # /api/logs/* (structured log viewer)
│   │   └── services/             # Business logic layer
│   │       ├── opensearch.py     # OpenSearch queries + aggregations
│   │       ├── graph.py          # Knowledge graph CRUD
│   │       ├── chunks.py         # Chunk quality assessment + editing
│   │       ├── query_playground.py  # Query execution + comparison
│   │       └── eval.py           # QA generation + evaluation scoring
│   │
│   └── frontend/                 # Next.js 16 admin UI
│       ├── Dockerfile
│       ├── package.json
│       ├── src/
│       │   ├── app/              # App router pages
│       │   │   ├── page.tsx            # Dashboard home
│       │   │   ├── documents/          # Document management
│       │   │   ├── graph/              # Knowledge graph explorer
│       │   │   ├── playground/         # Query playground
│       │   │   ├── chunks/             # Chunk inspector
│       │   │   ├── eval/              # Evaluation system
│       │   │   └── logs/               # Log viewer
│       │   ├── components/       # 37+ React components
│       │   ├── hooks/            # Custom React hooks (use-api, use-ws)
│       │   └── lib/              # API client utilities
│       └── public/               # Static assets
│
├── openclaw/                     # OpenClaw integration
│   ├── SETUP.md                  # Setup guide
│   ├── plugin/insurance-rag/     # OpenClaw MCP plugin (TypeScript)
│   │   ├── index.ts              # Static tool registration + lazy bridge
│   │   └── mcp-bridge.ts        # MCP client — spawns Python, manages lifecycle
│   └── katrina/                  # Katrina agent configuration
│       ├── IDENTITY.md           # Agent identity definition
│       ├── SOUL.md               # Personality and principles
│       ├── AGENTS.md             # Operating rules
│       ├── TOOLS.md              # Environment and tool descriptions
│       ├── HEARTBEAT.md          # Periodic tasks (inbox polling every 5 min)
│       └── USER.md               # User profile template
│
├── docker/                       # Deployment configs
│   ├── docker-compose.yml        # Full stack (OpenSearch, Dashboards, Admin, Caddy)
│   └── Caddyfile                 # Reverse proxy rules
│
├── tests/                        # Python test suite
│   ├── conftest.py               # Fixtures and dependency mocks
│   ├── test_config.py
│   ├── test_server.py
│   ├── test_ingestion.py
│   ├── test_rag.py
│   ├── test_metadata.py
│   ├── test_logging_service.py
│   ├── test_integration.py
│   └── admin/                    # Admin backend tests
│
├── data/                         # Document storage
│   ├── inbox/                    # Drop PDFs here for ingestion
│   ├── processed/                # Successfully ingested (moved here)
│   └── failed/                   # Failed ingestion (moved here)
│
├── docs/superpowers/             # Design documentation
│   ├── specs/                    # Detailed specifications
│   └── plans/                    # Implementation plans
│
├── .env.example                  # Environment template
├── pyproject.toml                # Python project config (uv/pip)
├── setup.sh                      # One-time setup script
├── start.sh                      # Start all services
└── stop.sh                       # Stop all services
```

---

## Prerequisites

- **Python 3.12** (required — MinerU does not support 3.14)
- **Node.js 20+** and **pnpm** (for admin frontend development)
- **Docker** and **Docker Compose** (for OpenSearch and deployment)
- **Apple Silicon Mac** (recommended — MinerU uses Metal GPU acceleration via MLX)
- **[uv](https://docs.astral.sh/uv/)** (recommended Python package manager)
- API keys for an OpenAI-compatible provider (default: YIBU API)

---

## Installation

### 1. Clone and configure

```bash
git clone https://github.com/weiexperimental/GEO-Insurance-RAG.git
cd GEO-Insurance-RAG
cp .env.example .env
# Edit .env — fill in your API keys (see Configuration section below)
```

### 2. Set up Python environment

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

This installs:
- `raganything[all]>=1.2.9` — RAG engine with all backends
- `mineru[mlx]>=2.7.6` — PDF parser with Metal acceleration
- `fastmcp>=3.1.1` — MCP server framework
- `opensearch-py>=3.1.0` — OpenSearch client
- `watchdog>=6.0.0` — File system monitoring
- `python-dotenv>=1.2.2` — Environment loading
- Dev: `pytest`, `pytest-asyncio`

### 3. Start OpenSearch

```bash
docker compose -f docker/docker-compose.yml up -d opensearch opensearch-dashboards
# Wait ~30 seconds for OpenSearch to initialize
```

### 4. Verify installation

```bash
python -m pytest tests/ -v
```

---

## Configuration

All configuration is loaded from environment variables (`.env` file). Copy `.env.example` and fill in the required values.

### Required Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for the LLM provider (knowledge graph construction, query routing) | — |
| `EMBEDDING_API_KEY` | API key for the embedding provider | — |
| `VISION_API_KEY` | API key for the vision model (image/table processing in PDFs) | — |

### Model Configuration

Each model (LLM, embedding, vision) has its own API key, base URL, and model name — allowing you to use different providers for each.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `gpt-4o-mini` | Model for knowledge graph + query routing |
| `LLM_API_BASE` | `https://yibuapi.com/v1` | LLM provider base URL |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model (3072 dimensions) |
| `EMBEDDING_API_BASE` | `https://yibuapi.com/v1` | Embedding provider base URL |
| `VISION_MODEL` | `gpt-4o-mini` | Vision model for image/table parsing |
| `VISION_API_BASE` | `https://yibuapi.com/v1` | Vision provider base URL |

### OpenSearch

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENSEARCH_HOST` | `localhost` | OpenSearch host |
| `OPENSEARCH_PORT` | `9200` | OpenSearch port |

### MinerU (PDF Parser)

| Variable | Default | Description |
|----------|---------|-------------|
| `MINERU_DEVICE` | `mps` | Compute device (`mps` for Apple Silicon, `cuda` for NVIDIA) |
| `MINERU_LANG` | `ch` | OCR language (Chinese) |
| `MINERU_PARSE_METHOD` | `auto` | Parsing method (`auto`, `ocr`, `txt`) |

### File Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `INBOX_DIR` | `./data/inbox` | Directory to drop PDFs for ingestion |
| `PROCESSED_DIR` | `./data/processed` | Where successfully ingested PDFs are moved |
| `FAILED_DIR` | `./data/failed` | Where failed PDFs are moved |
| `LOG_DIR` | `./logs` | Structured log file output directory |
| `MAX_FILE_SIZE_MB` | `100` | Maximum PDF file size in megabytes |

### OpenClaw Gateway Callback (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLAW_HOOKS_TOKEN` | — | Token for authenticating callback notifications |
| `OPENCLAW_GATEWAY_PORT` | `18789` | Gateway port for callback delivery |
| `OPENCLAW_NOTIFY_TO` | — | User/channel to notify on ingestion completion |

### Admin Dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_HOST` | `0.0.0.0` | Admin backend bind address |
| `ADMIN_PORT` | `8080` | Admin backend port |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost` | Allowed CORS origins (comma-separated) |

---

## Running the Services

### MCP Server Only (Development)

```bash
PYTHONPATH=. python src/server.py
```

The server starts in stdio mode by default, ready for MCP client connections.

### Admin Dashboard (Development)

```bash
# Terminal 1 — Backend
cd admin/backend
uvicorn admin.backend.main:app --host 0.0.0.0 --port 8080 --reload

# Terminal 2 — Frontend
cd admin/frontend
pnpm install
pnpm dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- OpenSearch Dashboards: http://localhost:5601

### Full Stack (Production)

```bash
docker compose -f docker/docker-compose.yml up -d
```

This starts all 5 services behind a Caddy reverse proxy on port 80. See the [Deployment](#deployment) section for details.

### Helper Scripts

```bash
./setup.sh   # One-time setup (venv, dependencies, Docker)
./start.sh   # Start all services
./stop.sh    # Stop all services
```

---

## MCP Tools

The server exposes 6 tools through the MCP protocol:

### `query`

Search insurance products using semantic search combined with knowledge graph traversal.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | string | required | Natural language question |
| `mode` | string | `"hybrid"` | Search mode: `local`, `global`, `hybrid`, `naive` |
| `top_k` | int | `10` | Maximum results to return |

**Modes explained:**
- **`local`** — Entity-centric retrieval from the knowledge graph neighborhood
- **`global`** — Community-level summarization across the full graph
- **`hybrid`** — Combines local + global (recommended for most queries)
- **`naive`** — Direct vector similarity search without graph augmentation

### `ingest`

Ingest a single PDF document. Returns immediately (fire-and-forget) — processing continues in the background.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | string | Absolute or relative path to the PDF |

**Pipeline:** Validate → Parse (MinerU) → Build graph (LightRAG) → Extract metadata (LLM) → Move to processed/ → Notify gateway

### `ingest_all`

Process all PDF files in the inbox directory. Documents are processed **sequentially** (GPU lock — one at a time).

### `list_documents`

List all indexed documents with filtering.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | `null` | Filter: `processed`, `processing`, `failed`, `pending` |
| `company` | string | `null` | Filter by insurance company |
| `product_type` | string | `null` | Filter by product type |
| `limit` | int | `20` | Results per page |
| `offset` | int | `0` | Pagination offset |

### `delete_document`

Remove a document and all its associated data (chunks, entities, relations).

| Parameter | Type | Description |
|-----------|------|-------------|
| `document_id` | string | The document ID (format: `doc-{md5hash}`) |
| `confirm` | bool | Must be `true` — safety confirmation |

### `get_system_status`

Returns system health: OpenSearch cluster status, index counts, inbox file count, and service availability.

---

## Admin Dashboard

The admin dashboard provides a web UI for managing and inspecting the RAG system.

### Pages

#### Dashboard (`/`)
System overview — document counts, ingestion status, cluster health.

#### Documents (`/documents`)
Full document management:
- List all documents with status badges (processed, processing, failed, pending)
- Filter by status, company, product type
- View document details: metadata, chunks, related entities
- Delete documents
- View ingestion analytics

#### Knowledge Graph (`/graph`)
Interactive graph explorer using [reagraph](https://github.com/reaviz/reagraph):
- Visualize entities and relationships
- Filter by entity type, linked document, max node count
- Search entities (fuzzy matching)
- View popular entities
- Entity detail panel with connections
- **Entity Resolution** — find and merge similar/duplicate entities using KNN + Jaccard similarity
- Edit entity descriptions, delete entities
- Edit and delete relations

#### Chunk Inspector (`/chunks`)
Inspect and manage document chunks:
- Quality assessment badges: **good**, **warning**, **bad**
  - Bad: noise type, empty content, < 10 tokens
  - Warning: 10–50 tokens, > 2000 tokens, malformed tables
  - Good: everything else
- Edit chunk content (re-embeds automatically)
- Delete individual or batch-delete chunks
- Token distribution histogram
- Quality stats overview

#### Query Playground (`/playground`)
Test and tune RAG queries:
- Full query mode (retrieval + LLM-generated response)
- Retrieve-only mode (raw retrieval results)
- **Compare mode** — run the same query with two different parameter sets side-by-side
- Timing metrics for each query

#### Evaluation (`/eval`)
Ground-truth evaluation system:
- **QA Pairs** — create manually or generate from document chunks using LLM
  - Categories: product_detail, pricing, eligibility, claim, general
  - Status: active, draft, archived
- **Evaluation Runs** — compare RAG answers against expected answers
  - Scores on 3 metrics: answer_correctness, faithfulness, context_relevancy
  - Run history with detailed results

#### Logs (`/logs`)
Structured log viewer:
- Browse logs by date
- Search by keyword
- JSON-formatted entries with stage, status, duration

### Real-Time Updates

The dashboard uses WebSocket connections for live updates:
- **System health** — polled every 15 seconds
- **Ingestion status** — polled every 5 seconds (broadcasts diffs only)
- **Logs** — polled every 2 seconds
- New WebSocket clients receive a full snapshot on connect

---

## OpenClaw Integration

### MCP Server Configuration

Add to `~/.openclaw/openclaw.json`:

```json
{
  "mcpServers": {
    "insurance-rag": {
      "command": "/path/to/GEO-Insurance-RAG/.venv/bin/python",
      "args": ["src/server.py"],
      "cwd": "/path/to/GEO-Insurance-RAG",
      "env": {
        "PYTHONPATH": "/path/to/GEO-Insurance-RAG"
      },
      "transport": "stdio"
    }
  }
}
```

### OpenClaw Plugin

The OpenClaw plugin (`openclaw/plugin/insurance-rag/`) bridges the MCP server to the OpenClaw agent system.

**Key architecture decision:** All `api.registerTool()` calls must happen synchronously inside `register()`. The plugin uses a **lazy-connect** pattern — the MCP bridge only connects on the first tool call, not at registration time.

- `index.ts` — Static tool definitions registered synchronously in `register()`
- `mcp-bridge.ts` — `McpBridge` class that spawns the Python MCP server process, manages connection lifecycle, and handles timeouts (60s connect, 30s per call)

Install the plugin:
```bash
cp -r openclaw/plugin/insurance-rag ~/.openclaw/extensions/insurance-rag
```

### Katrina Agent

The `openclaw/katrina/` directory contains configuration files for the "Katrina" AI agent persona that uses the insurance RAG tools:
- **IDENTITY.md** — Who Katrina is
- **SOUL.md** — Personality, tone, operating principles
- **AGENTS.md** — Rules for tool usage and response formatting
- **HEARTBEAT.md** — Periodic tasks (e.g., check inbox every 5 minutes)

---

## Document Ingestion Pipeline

### Flow

```
PDF dropped in inbox/
        │
        ▼
┌─ Validation ─────────────────────────────┐
│  • File exists and is readable            │
│  • File extension is .pdf                 │
│  • File size ≤ 100 MB (configurable)      │
└──────────────┬───────────────────────────┘
               │
               ▼
┌─ 3-Layer Deduplication ──────────────────┐
│  1. In-memory guard (skip if processing)  │
│  2. doc_status check (skip if processed)  │
│  3. File existence re-check               │
└──────────────┬───────────────────────────┘
               │
               ▼
┌─ PDF Parsing (MinerU) ──────────────────┐
│  • OCR with lang="ch" (Chinese)          │
│  • Metal GPU acceleration on ARM64       │
│  • Output: Markdown + images             │
│  • Retry: 3 attempts, exponential backoff │
│    (5s → 15s → 45s)                      │
└──────────────┬───────────────────────────┘
               │
               ▼
┌─ RAG Processing (RAGAnything) ──────────┐
│  • Chunk text and tables                  │
│  • Generate embeddings (3072-dim)         │
│  • Build knowledge graph entities/edges   │
│  • Store in OpenSearch indices            │
└──────────────┬───────────────────────────┘
               │
               ▼
┌─ Metadata Extraction (LLM) ─────────────┐
│  • company (e.g., AXA, Manulife)         │
│  • product_name                           │
│  • product_type (醫療/儲蓄/人壽/危疾/...) │
│  • document_type (小冊子/單張/指引/...)    │
│  • document_date                          │
└──────────────┬───────────────────────────┘
               │
               ▼
┌─ Post-Processing ────────────────────────┐
│  • Update doc_status with metadata        │
│  • Move PDF to processed/ directory       │
│  • Notify OpenClaw gateway (optional)     │
└──────────────────────────────────────────┘
```

### Deduplication

Document IDs are **deterministic** — computed as `doc-{md5(file_content)}`. This means:
- Re-dropping the same PDF is automatically skipped
- Different versions of the same product generate different IDs

### Sequential Processing

A single async lock ensures only **one document is processed at a time**. This is intentional — MinerU's GPU parsing is the bottleneck, and concurrent processing would cause OOM or contention on the Metal GPU.

### Retry Logic

Failed parsing attempts retry with exponential backoff:
- Attempt 1: immediate
- Attempt 2: wait 5 seconds
- Attempt 3: wait 15 seconds
- Attempt 4 (final): wait 45 seconds
- If all attempts fail: PDF moves to `failed/`, doc_status set to `failed`

---

## RAG Engine

### How It Works

The RAG engine combines two retrieval strategies:

1. **Vector Search** — Standard semantic similarity using `text-embedding-3-large` (3072 dimensions) stored in OpenSearch's KNN indices
2. **Knowledge Graph Retrieval** — LightRAG builds a knowledge graph from document content, enabling multi-hop reasoning across entities and relationships

### Query Modes

| Mode | Strategy | Best For |
|------|----------|----------|
| `hybrid` | Local + Global graph + vector | General queries (default) |
| `local` | Entity neighborhood traversal | Specific product details |
| `global` | Community-level summarization | Broad comparisons |
| `naive` | Pure vector similarity | Simple keyword-style queries |

### Vision Model Integration

When PDFs contain images or complex tables, MinerU extracts them and RAGAnything processes them through the vision model. The engine intercepts `image_data` kwargs and converts them to the standard OpenAI vision API format (base64 image in message content).

### OpenSearch Indices

| Index | Storage Type | Purpose |
|-------|-------------|---------|
| `text_chunks` | Vector (KNN) | Document chunks with 3072-dim embeddings |
| `chunks` | Document | Raw chunk content and metadata |
| `chunk_entity_relation-nodes` | Document | Knowledge graph entity nodes |
| `chunk_entity_relation-edges` | Document | Knowledge graph relationship edges |
| `entities` | Vector (KNN) | Entity embeddings for similarity search |
| `doc_status` | Document | Ingestion status and document metadata |
| `llm_response_cache` | Key-Value | Cached LLM responses |
| `rag-logs` | Document | Structured ingestion/query logs |
| `eval_qa_pairs` | Document | Ground-truth QA pairs |
| `eval_runs` | Document | Evaluation run results |

---

## Knowledge Graph

LightRAG automatically extracts entities and relationships from document content during ingestion. The knowledge graph enables:

- **Multi-hop queries** — "Which critical illness plans cover Stage 0 cancer?" traverses product → coverage → condition entities
- **Cross-document reasoning** — Compare products from different companies through shared entities
- **Entity resolution** — The admin dashboard includes KNN + Jaccard similarity matching to find and merge duplicate entities

### Entity Types

Entities are automatically typed during extraction. Common types include:
- Insurance companies, product names, coverage types
- Medical conditions, claim procedures, pricing tiers
- Noise types (automatically filtered in the UI): footer, header, aside_text, content, data, UNKNOWN

### Graph Editing

Through the admin dashboard, you can:
- Edit entity descriptions
- Delete entities and their associated relations
- Merge duplicate entities (combines descriptions, redirects relations)
- Edit relation descriptions and weights
- Delete relations

---

## Evaluation System

The evaluation system helps measure and improve RAG quality.

### QA Pair Management

- **Manual creation** — Write question/expected-answer pairs by hand
- **LLM generation** — Automatically generate QA pairs from good-quality chunks, categorized as:
  - `product_detail` — Product features and benefits
  - `pricing` — Premium and payment information
  - `eligibility` — Age, health, application requirements
  - `claim` — Claim procedures and documentation
  - `general` — General product information

### Evaluation Runs

An evaluation run:
1. Takes all active QA pairs
2. Runs each question through the RAG pipeline
3. Compares the actual answer against the expected answer using LLM scoring
4. Scores on 3 metrics (0–1 scale):
   - **Answer Correctness** — Does the answer match the expected content?
   - **Faithfulness** — Is the answer grounded in retrieved context?
   - **Context Relevancy** — Are the retrieved chunks relevant to the question?

---

## Deployment

### Docker Compose (Full Stack)

```bash
docker compose -f docker/docker-compose.yml up -d
```

This starts 5 services:

| Service | Port | Description |
|---------|------|-------------|
| `opensearch` | 9200 (localhost only) | OpenSearch 3.0.0 — single-node, security disabled |
| `opensearch-dashboards` | 5601 (localhost only) | Debug UI for OpenSearch |
| `admin-backend` | 8080 (internal) | FastAPI admin API |
| `admin-frontend` | 3000 (internal) | Next.js admin UI |
| `caddy` | **80** | Reverse proxy — public entry point |

### Caddy Routing

```
:80 {
    /api/*  → admin-backend:8080
    /ws     → admin-backend:8080
    /*      → admin-frontend:3000
}
```

### Health Checks

- **OpenSearch:** `curl http://localhost:9200/_cluster/health` — 10s interval, 30s startup grace
- **Admin Backend:** `curl http://localhost:8080/api/system/health` — 10s interval, 15s startup grace

### Tailscale Support

The deployment supports [Tailscale](https://tailscale.com/) for secure remote access. Configure in your environment to expose the Caddy proxy through your tailnet.

### Persistent Volumes

- `opensearch-data` — OpenSearch index data (survives container restarts)
- `caddy-data` — Caddy certificates and state

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_server.py -v

# Run admin backend tests
python -m pytest tests/admin/ -v
```

### Test Coverage

| Test File | What It Tests |
|-----------|---------------|
| `test_config.py` | Config loading, defaults, required key validation |
| `test_server.py` | Tool registration (6 tools), file validation, empty inbox, batch processing, delete confirmation, disconnected status |
| `test_ingestion.py` | PDF validation, size limits, 3-layer deduplication, metadata extraction, retry logic, file movement |
| `test_rag.py` | RAG engine initialization |
| `test_metadata.py` | LLM metadata extraction, JSON parsing fallback |
| `test_logging_service.py` | JSON log format, daily rotation |
| `test_integration.py` | End-to-end ingestion + query flow |

Tests use mock fixtures (`tests/conftest.py`) for external dependencies (LightRAG, RAGAnything, OpenSearch) so they run without infrastructure.

---

## Design Decisions

### Why MCP?

MCP (Model Context Protocol) is a standard for connecting AI agents to external tools. By implementing an MCP server, any MCP-compatible agent (Claude, OpenClaw, etc.) can use the insurance RAG without custom integration code.

### Why OpenSearch for Everything?

OpenSearch serves as the **unified storage backend** — vectors, graph data, key-value pairs, document status, logs, and evaluation data all live in one system. This eliminates the need for separate databases (no Postgres, no Redis, no Neo4j) and simplifies deployment.

### Why Sequential Ingestion?

MinerU's GPU-based PDF parsing is memory-intensive on Apple Silicon. Concurrent document processing causes Metal GPU memory pressure and crashes. The single-document async lock ensures stability at the cost of throughput.

### Why Fire-and-Forget?

The `ingest` tool returns immediately after validation. PDF parsing can take 30–120+ seconds depending on document complexity. Fire-and-forget allows the MCP client (AI agent) to continue interacting with the user while ingestion happens in the background. The optional gateway callback notifies the user when processing completes.

### Why Deterministic Document IDs?

Document IDs are `doc-{md5(content)}`. This provides natural deduplication — dropping the same PDF twice is a no-op — and makes document references stable and reproducible.

### Why Chinese OCR by Default?

This system is designed for Hong Kong insurance documents, which are primarily in Traditional Chinese. MinerU's `lang="ch"` setting optimizes OCR accuracy for Chinese characters.

### Why Separate API Keys per Model?

Different models may live on different providers or have different rate limits. Separating LLM, embedding, and vision keys provides maximum flexibility — you can use a fast/cheap model for vision, a high-quality model for LLM, and a specialized model for embeddings.

---

## Troubleshooting

### OpenSearch won't start

```bash
# Check Docker logs
docker compose -f docker/docker-compose.yml logs opensearch

# Common fix: increase vm.max_map_count (Linux)
sudo sysctl -w vm.max_map_count=262144

# macOS: Docker Desktop → Settings → Resources → increase memory to 4GB+
```

### MinerU GPU errors

```bash
# Verify Metal is available
python -c "import torch; print(torch.backends.mps.is_available())"

# Fallback to CPU if needed
MINERU_DEVICE=cpu python src/server.py
```

### Ingestion stuck or failed

```bash
# Check document status via MCP
# Use get_system_status tool or admin dashboard

# Check logs
ls logs/
cat logs/rag-$(date +%Y-%m-%d).log | python -m json.tool

# Manually retry: move PDF back to inbox
mv data/failed/document.pdf data/inbox/
```

### Admin dashboard can't connect

```bash
# Verify backend is running
curl http://localhost:8080/api/system/health

# Check CORS origins in .env
CORS_ORIGINS=http://localhost:3000,http://localhost

# Check WebSocket connection in browser console
```

---

## Debug UIs

- **Admin Dashboard:** http://localhost:3000 (or port 80 via Caddy)
- **OpenSearch Dashboards:** http://localhost:5601

---

## License

Private repository — all rights reserved.
