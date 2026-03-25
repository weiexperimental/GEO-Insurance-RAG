# TOOLS.md - Katrina 環境配置

## MCP Server: insurance-rag

- **Transport:** stdio
- **Command:** `.venv/bin/python src/server.py`
- **Working directory:** /path/to/GEO-Insurance-RAG
- **PYTHONPATH:** /path/to/GEO-Insurance-RAG

### 可用 Tools（6 個）

| Tool | 用途 |
|------|------|
| `query` | 自然語言搜尋保險產品資料 |
| `ingest` | 入庫指定 PDF（傳入 file_path） |
| `ingest_all` | 入庫 inbox 所有 PDF |
| `list_documents` | 列出文件，支援 status/company/product_type filter |
| `delete_document` | 刪除文件（需 confirm=true） |
| `get_system_status` | 系統健康、文件數量、inbox 狀態 |

## 文件目錄

- **Inbox:** `data/inbox/` — PDF 放入呢度，用 `ingest` 或 `ingest_all` 入庫
- **Processed:** `data/processed/` — 成功入庫嘅 PDF 搬到呢度
- **Failed:** `data/failed/` — 入庫失敗嘅 PDF 搬到呢度

## 文件上傳

- **WhatsApp 上傳：** Hook 自動 copy 去 inbox，你 call `ingest(file_path)` 入庫
- **手動拉文件：** 放入 `data/inbox/`，你 call `ingest_all` 處理

## 基礎設施

- **OpenSearch 3.x** — port 9200（vector、graph、KV、doc status 統一儲存）
- **MinerU (MLX GPU)** — PDF 解析，中文 OCR（`lang="ch"`, `device="mps"`）
- **YIBU API** — LLM / embedding / vision provider（OpenAI 兼容）
  - LLM: `gpt-4o-mini`
  - Embedding: `text-embedding-3-large`（3072 維度）
  - Vision: `gpt-4o-mini`

## 數據追蹤

- **唯一 source of truth：** LightRAG `doc_status` index（OpenSearch）
- 所有文件狀態、metadata 都喺 `doc_status` 入面
- `list_documents` 直接查詢 `doc_status` index

## 支援嘅文件格式

- 只限 PDF（最大 100MB）
- 語言：繁體中文
- 其他格式一律拒絕
