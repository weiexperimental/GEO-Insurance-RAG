# TOOLS.md - Katrina 環境配置

## MCP Server: insurance-rag

- **Transport:** stdio
- **Command:** `.venv/bin/python src/server.py`
- **Working directory:** /path/to/GEO-Insurance-RAG
- **PYTHONPATH:** /path/to/GEO-Insurance-RAG

## 文件目錄

- **Inbox:** `data/inbox/` — 手動拉 PDF 入呢度，heartbeat 會自動入庫
- **Processed:** `data/processed/` — 成功入庫嘅 PDF 搬到呢度
- **Failed:** `data/failed/` — 入庫失敗嘅 PDF 搬到呢度
- **Logs:** `logs/` — JSON 格式日誌

## 文件上傳

- **WhatsApp 上傳：** 你直接 call `ingest_document(file_path)` 入庫
- **手動拉文件：** 放入 `data/inbox/`，heartbeat 自動處理

## 基礎設施

- **OpenSearch 3.x** — port 9200（vector、graph、KV、doc status、ingestion status 統一儲存）
- **MinerU (MLX GPU)** — PDF 解析，中文 OCR（`lang="ch"`, `device="mps"`）
- **YIBU API** — LLM / embedding / vision provider（OpenAI 兼容）
  - LLM: `gpt-4o-mini`
  - Embedding: `text-embedding-3-large`（3072 維度）
  - Vision: `gpt-4o-mini`

## 支援嘅文件格式

- 只限 PDF（最大 100MB）
- 語言：繁體中文
- 其他格式一律拒絕
