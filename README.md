# GEO Insurance RAG — MCP Server

MCP server providing RAG search over Hong Kong insurance product documents.

## Quick Start

1. Copy `.env.example` to `.env` and fill in API keys
2. Start OpenSearch: `docker compose -f docker/docker-compose.yml up -d`
3. Install: `uv venv && uv pip install -e ".[dev]"`
4. Run: `python src/server.py`

## OpenClaw MCP Config

Add to `~/.openclaw/openclaw.json`:

```json
{
  "mcpServers": {
    "insurance-rag": {
      "command": "python",
      "args": ["src/server.py"],
      "cwd": "/path/to/GEO-Insurance-RAG",
      "transport": "stdio"
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| query | Search insurance products with semantic search + knowledge graph |
| ingest_inbox | Process all PDFs in inbox/ |
| ingest_document | Process a single PDF |
| get_doc_status | Check document processing status |
| list_documents | List indexed documents |
| delete_document | Remove a document |
| get_system_status | System health check |
| confirm_version_update | Confirm document version replacement |

## Debug UIs

- LightRAG WebUI: http://localhost:9621
- OpenSearch Dashboards: http://localhost:5601
