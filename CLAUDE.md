# GEO Insurance RAG — MCP Server

## 項目簡介

呢個係一個 MCP (Model Context Protocol) RAG server，專門為香港保險經紀設計。經紀透過 OpenClaw（AI gateway）連接呢個 MCP server，用自然語言查詢唔同保險公司嘅產品資料，唔使自己翻閱文件。

## 技術棧

- **Python 3.12**（必須，mineru 唔支援 3.14）
- **RAG-Anything + LightRAG** — multimodal RAG 引擎 + 知識圖譜
- **MinerU (MLX GPU)** — PDF 解析（Mac ARM64 Metal 加速）
- **OpenSearch 3.x** — 統一儲存（vector、graph、KV、doc status）
- **FastMCP 3.x** — MCP server framework
- **YIBU API** — LLM/embedding/vision provider（OpenAI 兼容）
- **OpenClaw heartbeat** — 定期 inbox 檢查 + 入庫狀態通知

## 關鍵設計決定

- 回答語言：統一中文
- 文件格式：只支援 PDF
- MinerU 語言：`lang="ch"`（中文 OCR）
- Embedding：`text-embedding-3-large`（3072 維度）
- 內部 LLM + Vision：`gpt-4o-mini` via YIBU API
- OpenSearch port：**9200**（預設）
- MCP 傳輸：stdio + Streamable HTTP
- 入庫：逐份順序處理，3 次 retry + exponential backoff
- 版本管理：保留舊版標記過時，自動配對 + 用戶確認
- Vision model：攔截 `image_data` kwarg，轉換為標準 OpenAI vision 格式

## 重要文件

- `docs/superpowers/specs/2026-03-22-mcp-rag-insurance-design.md` — 完整設計 spec
- `docs/superpowers/plans/2026-03-22-mcp-rag-insurance-plan.md` — 實現計劃
- `src/server.py` — MCP server 入口（8 個 tools）
- `src/rag.py` — RAG engine wrapper
- `src/ingestion.py` — 入庫 pipeline
- `docker/docker-compose.yml` — OpenSearch Docker 配置

## Setup 步驟

```bash
git clone https://github.com/weiexperimental/GEO-Insurance-RAG.git
cd GEO-Insurance-RAG
cp .env.example .env  # 填入 YIBU API keys
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install "raganything>=1.2.9" "mineru[mlx]>=2.7.6" fastmcp watchdog opensearch-py python-dotenv pytest pytest-asyncio
docker compose -f docker/docker-compose.yml up -d
# 等 ~30s OpenSearch 啟動
python -m pytest tests/ -v  # 20 tests should pass
```

## 運行 MCP Server

```bash
PYTHONPATH=. python src/server.py
```

## OpenClaw MCP 配置

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

## 用戶偏好

- 用廣東話溝通
- 盡量用現成工具/library，自己寫越少 code 越好
- 每個 model（LLM、embedding、vision）獨立 API key + base URL
- 文件只入繁體中文版
