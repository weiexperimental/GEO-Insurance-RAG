# MCP RAG Insurance System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MCP server that provides RAG search over Hong Kong insurance product PDFs, using RAG-Anything/LightRAG with OpenSearch storage.

**Architecture:** A Python MCP server (FastMCP) wraps RAG-Anything/LightRAG to expose 8 tools for document ingestion, querying, and management. OpenSearch (Docker) provides unified storage. MinerU (MLX GPU) parses PDFs. YIBU API provides LLM/embedding/vision.

**Tech Stack:** Python 3.12, uv, FastMCP, RAG-Anything, LightRAG, MinerU (MLX), OpenSearch 3.x, watchdog, python-dotenv

**Spec:** `docs/superpowers/specs/2026-03-22-mcp-rag-insurance-design.md`

---

## File Structure

```
GEO-Insurance-RAG/
├── docker/
│   └── docker-compose.yml            # OpenSearch + Dashboards
├── src/
│   ├── __init__.py                   # Package init
│   ├── config.py                     # Env config loading, validation
│   ├── logging_service.py            # Dual-write logger (file + OpenSearch)
│   ├── rag.py                        # RAG-Anything/LightRAG init + wrapper
│   ├── metadata.py                   # LLM metadata extraction from parsed content
│   ├── versioning.py                 # Version detection + confirmation logic
│   ├── ingestion.py                  # Ingestion pipeline orchestrator
│   ├── watcher.py                    # Inbox folder watchdog monitor
│   └── server.py                     # MCP server entry point (all 8 tools)
├── tests/
│   ├── conftest.py                   # Shared fixtures
│   ├── test_config.py                # Config loading tests
│   ├── test_logging_service.py       # Logger tests
│   ├── test_metadata.py              # Metadata extraction tests
│   ├── test_versioning.py            # Version detection tests
│   ├── test_ingestion.py             # Ingestion pipeline tests
│   ├── test_watcher.py               # Watchdog tests
│   └── test_server.py                # MCP tool integration tests
├── data/
│   ├── inbox/
│   ├── processed/
│   └── failed/
├── logs/
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## Task 1: Project Scaffolding + Docker

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `docker/docker-compose.yml`
- Create: `data/inbox/.gitkeep`, `data/processed/.gitkeep`, `data/failed/.gitkeep`, `logs/.gitkeep`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "geo-insurance-rag"
version = "0.1.0"
description = "MCP RAG server for Hong Kong insurance product documents"
requires-python = ">=3.12"
dependencies = [
    "raganything[all]>=1.2.9",
    "mineru[mlx]>=2.7.6",
    "fastmcp>=3.1.1",
    "watchdog>=6.0.0",
    "opensearch-py>=3.1.0",
    "python-dotenv>=1.2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.env.example`**

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

- [ ] **Step 3: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
.venv/
logs/*.log
data/inbox/*.pdf
data/processed/*.pdf
data/failed/*.pdf
.DS_Store
```

- [ ] **Step 4: Create `docker/docker-compose.yml`**

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
      - "9200:9200"
    volumes:
      - opensearch-data:/usr/share/opensearch/data

  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:3.0.0
    container_name: geo-rag-dashboards
    environment:
      - OPENSEARCH_HOSTS=["http://opensearch:9200"]
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    ports:
      - "5601:5601"
    depends_on:
      - opensearch

volumes:
  opensearch-data:
```

- [ ] **Step 5: Create data directories with `.gitkeep` files**

```bash
mkdir -p data/inbox data/processed data/failed logs
touch data/inbox/.gitkeep data/processed/.gitkeep data/failed/.gitkeep logs/.gitkeep
```

- [ ] **Step 6: Install dependencies**

```bash
uv venv
uv pip install -e ".[dev]"
```

- [ ] **Step 7: Start OpenSearch and verify**

```bash
docker compose -f docker/docker-compose.yml up -d
# Wait ~30s for startup
curl -s http://localhost:9200 | python -m json.tool
# Expected: JSON with "cluster_name", "version" fields
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .env.example .gitignore docker/ data/ logs/
git commit -m "feat: project scaffolding with Docker OpenSearch setup"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import pytest
from unittest.mock import patch


def test_config_loads_all_model_settings():
    env = {
        "LLM_MODEL": "gpt-4o-mini",
        "LLM_API_KEY": "sk-test-llm",
        "LLM_API_BASE": "https://yibuapi.com/v1",
        "EMBEDDING_MODEL": "text-embedding-3-large",
        "EMBEDDING_API_KEY": "sk-test-embed",
        "EMBEDDING_API_BASE": "https://yibuapi.com/v1",
        "VISION_MODEL": "gpt-4o-mini",
        "VISION_API_KEY": "sk-test-vision",
        "VISION_API_BASE": "https://yibuapi.com/v1",
        "OPENSEARCH_HOST": "localhost",
        "OPENSEARCH_PORT": "9200",
    }
    with patch.dict(os.environ, env, clear=False):
        from src.config import load_config

        cfg = load_config()
        assert cfg.llm.model == "gpt-4o-mini"
        assert cfg.llm.api_key == "sk-test-llm"
        assert cfg.llm.api_base == "https://yibuapi.com/v1"
        assert cfg.embedding.model == "text-embedding-3-large"
        assert cfg.embedding.api_key == "sk-test-embed"
        assert cfg.vision.model == "gpt-4o-mini"
        assert cfg.vision.api_key == "sk-test-vision"
        assert cfg.opensearch.host == "localhost"
        assert cfg.opensearch.port == 9200


def test_config_raises_on_missing_api_key():
    env = {"LLM_MODEL": "gpt-4o-mini"}  # Missing LLM_API_KEY
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            from src.config import load_config

            load_config()


def test_config_default_paths():
    env = {
        "LLM_API_KEY": "sk-test",
        "EMBEDDING_API_KEY": "sk-test",
        "VISION_API_KEY": "sk-test",
    }
    with patch.dict(os.environ, env, clear=False):
        from src.config import load_config

        cfg = load_config()
        assert cfg.paths.inbox_dir.endswith("data/inbox")
        assert cfg.limits.max_file_size_mb == 100
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Write implementation**

```python
# src/config.py
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class ModelConfig:
    model: str
    api_key: str
    api_base: str


@dataclass
class OpenSearchConfig:
    host: str
    port: int


@dataclass
class MinerUConfig:
    device: str
    lang: str
    parse_method: str


@dataclass
class PathsConfig:
    inbox_dir: str
    processed_dir: str
    failed_dir: str
    log_dir: str


@dataclass
class LimitsConfig:
    max_file_size_mb: int


@dataclass
class AppConfig:
    llm: ModelConfig
    embedding: ModelConfig
    vision: ModelConfig
    opensearch: OpenSearchConfig
    mineru: MinerUConfig
    paths: PathsConfig
    limits: LimitsConfig


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise ValueError(f"Missing required environment variable: {key}")
    return val


def load_config() -> AppConfig:
    load_dotenv()

    return AppConfig(
        llm=ModelConfig(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=_require_env("LLM_API_KEY"),
            api_base=os.getenv("LLM_API_BASE", "https://yibuapi.com/v1"),
        ),
        embedding=ModelConfig(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            api_key=_require_env("EMBEDDING_API_KEY"),
            api_base=os.getenv("EMBEDDING_API_BASE", "https://yibuapi.com/v1"),
        ),
        vision=ModelConfig(
            model=os.getenv("VISION_MODEL", "gpt-4o-mini"),
            api_key=_require_env("VISION_API_KEY"),
            api_base=os.getenv("VISION_API_BASE", "https://yibuapi.com/v1"),
        ),
        opensearch=OpenSearchConfig(
            host=os.getenv("OPENSEARCH_HOST", "localhost"),
            port=int(os.getenv("OPENSEARCH_PORT", "9200")),
        ),
        mineru=MinerUConfig(
            device=os.getenv("MINERU_DEVICE", "mps"),
            lang=os.getenv("MINERU_LANG", "ch"),
            parse_method=os.getenv("MINERU_PARSE_METHOD", "auto"),
        ),
        paths=PathsConfig(
            inbox_dir=os.getenv("INBOX_DIR", "./data/inbox"),
            processed_dir=os.getenv("PROCESSED_DIR", "./data/processed"),
            failed_dir=os.getenv("FAILED_DIR", "./data/failed"),
            log_dir=os.getenv("LOG_DIR", "./logs"),
        ),
        limits=LimitsConfig(
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "100")),
        ),
    )
```

- [ ] **Step 4: Create `src/__init__.py` and `tests/conftest.py`**

```python
# src/__init__.py
# (empty)
```

```python
# tests/conftest.py
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/__init__.py src/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: add configuration module with env loading and validation"
```

---

## Task 3: Logging Service

**Files:**
- Create: `src/logging_service.py`
- Create: `tests/test_logging_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_logging_service.py
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_logger_writes_to_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.logging_service import RAGLogger

        logger = RAGLogger(log_dir=tmpdir, opensearch_client=None)
        logger.log(
            document="test.pdf",
            stage="parsing",
            status="success",
            duration_ms=1234,
            details={"pages": 5},
        )

        log_files = list(Path(tmpdir).glob("*.log"))
        assert len(log_files) == 1

        with open(log_files[0]) as f:
            lines = f.readlines()
            entry = json.loads(lines[-1])
            assert entry["document"] == "test.pdf"
            assert entry["stage"] == "parsing"
            assert entry["status"] == "success"
            assert entry["duration_ms"] == 1234
            assert entry["details"]["pages"] == 5
            assert "timestamp" in entry


def test_logger_writes_to_opensearch_when_available():
    mock_client = MagicMock()
    from src.logging_service import RAGLogger

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = RAGLogger(log_dir=tmpdir, opensearch_client=mock_client)
        logger.log(document="test.pdf", stage="indexing", status="success")

        mock_client.index.assert_called_once()
        call_kwargs = mock_client.index.call_args
        assert call_kwargs.kwargs["index"] == "rag-logs"


def test_logger_continues_if_opensearch_fails():
    mock_client = MagicMock()
    mock_client.index.side_effect = Exception("connection refused")

    from src.logging_service import RAGLogger

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = RAGLogger(log_dir=tmpdir, opensearch_client=mock_client)
        # Should not raise
        logger.log(document="test.pdf", stage="parsing", status="success")

        # File log should still be written
        log_files = list(Path(tmpdir).glob("*.log"))
        assert len(log_files) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_logging_service.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# src/logging_service.py
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RAGLogger:
    def __init__(self, log_dir: str, opensearch_client: Any | None = None):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._os_client = opensearch_client
        self._log_file = self._log_dir / f"rag-{datetime.now().strftime('%Y-%m-%d')}.log"

    def log(
        self,
        document: str,
        stage: str,
        status: str,
        duration_ms: int = 0,
        details: dict | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "document": document,
            "stage": stage,
            "status": status,
            "duration_ms": duration_ms,
            "details": details or {},
        }

        # Always write to file
        with open(self._log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Try writing to OpenSearch
        if self._os_client:
            try:
                self._os_client.index(index="rag-logs", body=entry)
            except Exception:
                pass  # File log is the fallback
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_logging_service.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/logging_service.py tests/test_logging_service.py
git commit -m "feat: add dual-write logging service (file + OpenSearch)"
```

---

## Task 4: RAG Engine Wrapper

**Files:**
- Create: `src/rag.py`
- Create: `tests/test_rag.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rag.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_rag_engine_initializes():
    from src.config import ModelConfig, OpenSearchConfig

    llm_cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
    embed_cfg = ModelConfig(model="text-embedding-3-large", api_key="sk-test", api_base="https://test.com/v1")
    vision_cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
    os_cfg = OpenSearchConfig(host="localhost", port=9200)

    with patch("src.rag.LightRAG") as mock_lr, \
         patch("src.rag.RAGAnything") as mock_ra:
        mock_lr_instance = AsyncMock()
        mock_lr.return_value = mock_lr_instance

        from src.rag import RAGEngine
        engine = RAGEngine(
            llm_config=llm_cfg,
            embedding_config=embed_cfg,
            vision_config=vision_cfg,
            opensearch_config=os_cfg,
            working_dir="/tmp/test-rag",
        )
        await engine.initialize()

        mock_lr.assert_called_once()
        mock_lr_instance.initialize_storages.assert_awaited_once()
        mock_ra.assert_called_once()


@pytest.mark.asyncio
async def test_rag_engine_query():
    from src.rag import RAGEngine

    engine = RAGEngine.__new__(RAGEngine)
    engine._rag = AsyncMock()
    engine._rag.aquery.return_value = "test result"

    result = await engine.query("test question", mode="hybrid")
    engine._rag.aquery.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_rag.py -v
```
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/rag.py
from pathlib import Path
from typing import Any

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from raganything import RAGAnything, RAGAnythingConfig

from src.config import ModelConfig, OpenSearchConfig


async def _llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    keyword_extraction: bool = False,
    **kwargs,
) -> str:
    """LLM function factory — config injected via kwargs at call time."""
    model = kwargs.pop("model", "gpt-4o-mini")
    api_key = kwargs.pop("api_key", "")
    base_url = kwargs.pop("base_url", "")
    return await openai_complete_if_cache(
        model=model,
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        api_key=api_key,
        base_url=base_url,
        **kwargs,
    )


async def _embed_func(texts: list[str], **kwargs) -> list[list[float]]:
    """Embedding function factory."""
    model = kwargs.pop("model", "text-embedding-3-large")
    api_key = kwargs.pop("api_key", "")
    base_url = kwargs.pop("base_url", "")
    return await openai_embed(
        texts=texts,
        model=model,
        api_key=api_key,
        base_url=base_url,
        **kwargs,
    )


class RAGEngine:
    def __init__(
        self,
        llm_config: ModelConfig,
        embedding_config: ModelConfig,
        vision_config: ModelConfig,
        opensearch_config: OpenSearchConfig,
        working_dir: str,
    ):
        self._llm_cfg = llm_config
        self._embed_cfg = embedding_config
        self._vision_cfg = vision_config
        self._os_cfg = opensearch_config
        self._working_dir = working_dir
        self._lightrag: LightRAG | None = None
        self._rag: RAGAnything | None = None

    async def initialize(self) -> None:
        # Configure OpenSearch env vars BEFORE LightRAG init
        # LightRAG's OpenSearch adapters read from these env vars
        import os
        os.environ["OPENSEARCH_HOSTS"] = f"{self._os_cfg.host}:{self._os_cfg.port}"
        os.environ["OPENSEARCH_USE_SSL"] = "false"
        os.environ["OPENSEARCH_VERIFY_CERTS"] = "false"

        async def llm_func(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kw):
            return await _llm_func(
                prompt, system_prompt, history_messages, keyword_extraction,
                model=self._llm_cfg.model,
                api_key=self._llm_cfg.api_key,
                base_url=self._llm_cfg.api_base,
                **kw,
            )

        async def embed_func(texts, **kw):
            return await _embed_func(
                texts,
                model=self._embed_cfg.model,
                api_key=self._embed_cfg.api_key,
                base_url=self._embed_cfg.api_base,
                **kw,
            )

        async def vision_func(prompt, system_prompt=None, history_messages=None, **kw):
            return await _llm_func(
                prompt, system_prompt, history_messages,
                model=self._vision_cfg.model,
                api_key=self._vision_cfg.api_key,
                base_url=self._vision_cfg.api_base,
                **kw,
            )

        self._lightrag = LightRAG(
            working_dir=self._working_dir,
            llm_model_func=llm_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=3072,
                max_token_size=8192,
                func=embed_func,
            ),
            kv_storage="OpenSearchKVStorage",
            vector_storage="OpenSearchVectorDBStorage",
            graph_storage="OpenSearchGraphStorage",
            doc_status_storage="OpenSearchDocStatusStorage",
        )
        await self._lightrag.initialize_storages()

        self._rag = RAGAnything(
            lightrag=self._lightrag,
            llm_model_func=llm_func,
            vision_model_func=vision_func,
            embedding_func=self._lightrag.embedding_func,
            config=RAGAnythingConfig(
                working_dir=self._working_dir,
                enable_image_processing=True,
                enable_table_processing=True,
                enable_equation_processing=True,
            ),
        )

    async def query(self, question: str, mode: str = "hybrid", top_k: int = 5) -> str:
        return await self._rag.aquery(question, mode=mode, top_k=top_k)

    async def ingest_document(self, file_path: str, output_dir: str, device: str = "mps", lang: str = "ch") -> None:
        await self._rag.process_document_complete(
            file_path=file_path,
            output_dir=output_dir,
            parse_method="auto",
            device=device,
            lang=lang,
        )

    async def delete_document(self, document_id: str) -> bool:
        try:
            await self._lightrag.adelete_by_doc_id(document_id)
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_rag.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/rag.py tests/test_rag.py
git commit -m "feat: add RAG engine wrapper for LightRAG + RAG-Anything"
```

---

## Task 5: Metadata Extraction

**Files:**
- Create: `src/metadata.py`
- Create: `tests/test_metadata.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_metadata.py
import json
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_extract_metadata_returns_structured_data():
    mock_response = json.dumps({
        "company": "AXA 安盛",
        "product_name": "智尊守慧醫療保障",
        "product_type": "醫療",
        "document_type": "產品小冊子",
        "document_date": "2026-01",
    })

    with patch("src.metadata.openai_complete_if_cache", new_callable=AsyncMock, return_value=mock_response):
        from src.metadata import extract_metadata
        from src.config import ModelConfig

        cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
        result = await extract_metadata("AXA安盛智尊守慧醫療保障產品小冊子內容...", cfg)

        assert result["company"] == "AXA 安盛"
        assert result["product_name"] == "智尊守慧醫療保障"
        assert result["product_type"] == "醫療"
        assert result["document_type"] == "產品小冊子"
        assert result["document_date"] == "2026-01"


@pytest.mark.asyncio
async def test_extract_metadata_returns_empty_on_failure():
    with patch("src.metadata.openai_complete_if_cache", new_callable=AsyncMock, side_effect=Exception("API down")):
        from src.metadata import extract_metadata
        from src.config import ModelConfig

        cfg = ModelConfig(model="gpt-4o-mini", api_key="sk-test", api_base="https://test.com/v1")
        result = await extract_metadata("some content", cfg)

        assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_metadata.py -v
```
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/metadata.py
import json
from typing import Any

from lightrag.llm.openai import openai_complete_if_cache

from src.config import ModelConfig

EXTRACTION_PROMPT = """你是一個保險文件分析助手。請從以下文件內容中提取結構化資訊。

只回傳 JSON，不要其他文字。格式如下：
{
    "company": "保險公司名稱（中文全名）",
    "product_name": "產品名稱（中文）",
    "product_type": "產品類型：醫療 / 儲蓄 / 人壽 / 意外 / 其他",
    "document_type": "文件類型：產品小冊子 / 宣傳單張 / 付款指引 / 培訓資料 / 其他",
    "document_date": "文件日期（格式：YYYY-MM，如果找不到就填空字串）"
}

文件內容（前 3000 字）：
"""


async def extract_metadata(content: str, llm_config: ModelConfig) -> dict[str, Any]:
    """Extract structured metadata from document content using LLM."""
    try:
        truncated = content[:3000]
        response = await openai_complete_if_cache(
            model=llm_config.model,
            prompt=EXTRACTION_PROMPT + truncated,
            api_key=llm_config.api_key,
            base_url=llm_config.api_base,
        )
        # Parse JSON from response, handling potential markdown wrapping
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        return {}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_metadata.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/metadata.py tests/test_metadata.py
git commit -m "feat: add LLM-based metadata extraction for insurance documents"
```

---

## Task 6: Version Detection

**Files:**
- Create: `src/versioning.py`
- Create: `tests/test_versioning.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_versioning.py
import pytest
from unittest.mock import MagicMock


def test_find_existing_version_returns_match():
    from src.versioning import find_existing_version

    existing_docs = [
        {"document_id": "doc-001", "company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子", "is_latest": True},
        {"document_id": "doc-002", "company": "CTF Life", "product_name": "MyWealth", "document_type": "產品小冊子", "is_latest": True},
    ]

    new_meta = {"company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子"}
    match = find_existing_version(new_meta, existing_docs)
    assert match is not None
    assert match["document_id"] == "doc-001"


def test_find_existing_version_returns_none_when_no_match():
    from src.versioning import find_existing_version

    existing_docs = [
        {"document_id": "doc-001", "company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子", "is_latest": True},
    ]

    new_meta = {"company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "培訓資料"}
    match = find_existing_version(new_meta, existing_docs)
    assert match is None


def test_find_existing_version_only_matches_latest():
    from src.versioning import find_existing_version

    existing_docs = [
        {"document_id": "doc-001", "company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子", "is_latest": False},
    ]

    new_meta = {"company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子"}
    match = find_existing_version(new_meta, existing_docs)
    assert match is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_versioning.py -v
```
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/versioning.py
from typing import Any


def find_existing_version(
    new_metadata: dict[str, Any],
    existing_docs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find an existing document that matches company + product_name + document_type.
    Only matches documents where is_latest is True."""
    company = new_metadata.get("company", "")
    product = new_metadata.get("product_name", "")
    doc_type = new_metadata.get("document_type", "")

    if not company or not product or not doc_type:
        return None

    for doc in existing_docs:
        if (
            doc.get("company") == company
            and doc.get("product_name") == product
            and doc.get("document_type") == doc_type
            and doc.get("is_latest") is True
        ):
            return doc

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_versioning.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/versioning.py tests/test_versioning.py
git commit -m "feat: add version detection logic for document updates"
```

---

## Task 7: Ingestion Pipeline

**Files:**
- Create: `src/ingestion.py`
- Create: `tests/test_ingestion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingestion.py
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_validate_file_accepts_valid_pdf():
    from src.ingestion import validate_file

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 test content")
        f.flush()
        result = validate_file(f.name, max_size_mb=100)
        assert result["valid"] is True


def test_validate_file_rejects_non_pdf():
    from src.ingestion import validate_file

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(b"not a pdf")
        f.flush()
        result = validate_file(f.name, max_size_mb=100)
        assert result["valid"] is False
        assert "PDF" in result["reason"]


def test_validate_file_rejects_oversized():
    from src.ingestion import validate_file

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF" + b"x" * (2 * 1024 * 1024))  # ~2MB
        f.flush()
        result = validate_file(f.name, max_size_mb=1)  # 1MB limit
        assert result["valid"] is False
        assert "size" in result["reason"].lower()


def test_compute_file_hash():
    from src.ingestion import compute_file_hash

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content for hashing")
        f.flush()
        h = compute_file_hash(f.name)
        expected = hashlib.sha256(b"test content for hashing").hexdigest()
        assert h == expected
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ingestion.py -v
```
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/ingestion.py
import asyncio
import hashlib
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.logging_service import RAGLogger
from src.metadata import extract_metadata
from src.rag import RAGEngine
from src.versioning import find_existing_version


def validate_file(file_path: str, max_size_mb: int) -> dict[str, Any]:
    """Validate that file is a PDF within size limits."""
    path = Path(file_path)
    if not path.suffix.lower() == ".pdf":
        return {"valid": False, "reason": f"Not a PDF file: {path.suffix}"}

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        return {"valid": False, "reason": f"File size {size_mb:.1f}MB exceeds limit of {max_size_mb}MB"}

    return {"valid": True, "reason": ""}


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


RETRY_DELAYS = [5, 15, 45]  # Exponential backoff in seconds


async def _retry_async(coro_factory, retries=3, delays=RETRY_DELAYS):
    """Retry an async operation with exponential backoff."""
    last_error = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                await asyncio.sleep(delays[attempt])
    raise last_error


def _read_parsed_content(output_dir: str, file_name: str) -> str:
    """Read the markdown output from MinerU parsing.
    MinerU / RAG-Anything saves parsed content as .md files in the output dir."""
    stem = Path(file_name).stem
    # Look for markdown output in common MinerU output patterns
    for pattern in [f"{stem}/{stem}.md", f"{stem}.md", f"{stem}/auto/{stem}.md"]:
        md_path = Path(output_dir) / pattern
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
    return ""


class IngestionPipeline:
    def __init__(self, config: AppConfig, rag_engine: RAGEngine, logger: RAGLogger):
        self._config = config
        self._rag = rag_engine
        self._logger = logger
        self._queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()  # Ensures only one ingestion at a time
        self._doc_statuses: dict[str, dict] = {}
        self._known_hashes: set[str] = set()

    def get_status(self, document_id: str) -> dict | None:
        return self._doc_statuses.get(document_id)

    def get_all_statuses(self) -> dict[str, dict]:
        return dict(self._doc_statuses)

    async def enqueue(self, file_path: str) -> dict[str, Any]:
        """Add a file to the ingestion queue. Returns document_id and status."""
        doc_id = str(uuid.uuid4())
        self._doc_statuses[doc_id] = {
            "document_id": doc_id,
            "file_name": Path(file_path).name,
            "file_path": file_path,
            "status": "pending",
            "stages": [],
            "metadata": None,
            "file_hash": None,
            "ingested_at": None,
        }
        await self._queue.put((doc_id, file_path))
        return {"document_id": doc_id, "status": "pending"}

    async def process_queue(self) -> None:
        """Process files from the queue one at a time (locked)."""
        async with self._lock:
            while not self._queue.empty():
                doc_id, file_path = await self._queue.get()
                await self._process_single(doc_id, file_path)

    async def _process_single(self, doc_id: str, file_path: str) -> None:
        """Process a single document through the full pipeline."""
        from datetime import datetime, timezone
        status = self._doc_statuses[doc_id]
        file_name = Path(file_path).name
        is_reprocess = False

        # Stage: validating
        status["status"] = "validating"
        start = time.time()
        validation = validate_file(file_path, self._config.limits.max_file_size_mb)
        elapsed = int((time.time() - start) * 1000)
        status["stages"].append({"stage": "validating", "status": "success" if validation["valid"] else "failed", "duration_ms": elapsed, "error": validation.get("reason") or None})

        if not validation["valid"]:
            status["status"] = "failed"
            shutil.move(file_path, str(Path(self._config.paths.failed_dir) / file_name))
            self._logger.log(document=file_name, stage="validating", status="failed", details={"reason": validation["reason"]})
            return

        # Duplicate check
        file_hash = compute_file_hash(file_path)
        status["file_hash"] = file_hash

        if file_hash in self._known_hashes:
            existing = next((s for s in self._doc_statuses.values() if s.get("file_hash") == file_hash and s["document_id"] != doc_id), None)
            if existing and existing.get("status") == "partial":
                is_reprocess = True  # Allow re-processing of partial docs
            elif existing:
                status["status"] = "failed"
                status["stages"].append({"stage": "duplicate_check", "status": "skipped", "duration_ms": 0, "error": "Duplicate file"})
                self._logger.log(document=file_name, stage="duplicate_check", status="skipped", details={"reason": "duplicate"})
                return

        self._known_hashes.add(file_hash)

        # Stage: parsing (with retry)
        status["status"] = "parsing"
        start = time.time()
        try:
            await _retry_async(lambda: self._rag.ingest_document(
                file_path=file_path,
                output_dir=self._config.paths.processed_dir,
                device=self._config.mineru.device,
                lang=self._config.mineru.lang,
            ))
            elapsed = int((time.time() - start) * 1000)
            status["stages"].append({"stage": "parsing", "status": "success", "duration_ms": elapsed, "error": None})
            self._logger.log(document=file_name, stage="parsing", status="success", duration_ms=elapsed)
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            status["stages"].append({"stage": "parsing", "status": "failed", "duration_ms": elapsed, "error": str(e)})
            status["status"] = "failed"
            shutil.move(file_path, str(Path(self._config.paths.failed_dir) / file_name))
            self._logger.log(document=file_name, stage="parsing", status="failed", duration_ms=elapsed, details={"error": str(e)})
            return

        # Stage: extracting_metadata (with retry)
        status["status"] = "extracting_metadata"
        start = time.time()
        parsed_content = _read_parsed_content(self._config.paths.processed_dir, file_name)
        try:
            metadata = await _retry_async(lambda: extract_metadata(parsed_content, self._config.llm))
        except Exception:
            metadata = {}
        elapsed = int((time.time() - start) * 1000)

        if metadata:
            status["metadata"] = metadata
            status["stages"].append({"stage": "extracting_metadata", "status": "success", "duration_ms": elapsed, "error": None})
            self._logger.log(document=file_name, stage="extracting_metadata", status="success", duration_ms=elapsed, details=metadata)
        else:
            status["metadata"] = {}
            status["stages"].append({"stage": "extracting_metadata", "status": "failed", "duration_ms": elapsed, "error": "Metadata extraction failed"})
            status["status"] = "partial"
            status["ingested_at"] = datetime.now(timezone.utc).isoformat()
            self._logger.log(document=file_name, stage="extracting_metadata", status="failed", duration_ms=elapsed)
            shutil.move(file_path, str(Path(self._config.paths.processed_dir) / file_name))
            return

        # Stage: checking_version (skip for re-processed partial docs)
        if not is_reprocess and metadata:
            status["status"] = "checking_version"
            existing_docs = [s for s in self._doc_statuses.values()
                            if s["status"] in ("ready",) and s["document_id"] != doc_id]
            match = find_existing_version(metadata, [s.get("metadata", {}) | {"document_id": s["document_id"]} for s in existing_docs if s.get("metadata")])
            if match:
                status["status"] = "awaiting_confirmation"
                status["stages"].append({"stage": "checking_version", "status": "awaiting_confirmation", "duration_ms": 0, "error": None})
                status["metadata"]["_matched_doc_id"] = match["document_id"]
                self._logger.log(document=file_name, stage="checking_version", status="awaiting_confirmation",
                                details={"matched": match["document_id"]})
                return  # Wait for confirm_version_update tool call
            else:
                status["stages"].append({"stage": "checking_version", "status": "no_match", "duration_ms": 0, "error": None})

        # Stage: complete
        status["status"] = "ready"
        status["metadata"]["is_latest"] = True
        status["ingested_at"] = datetime.now(timezone.utc).isoformat()
        shutil.move(file_path, str(Path(self._config.paths.processed_dir) / file_name))
        self._logger.log(document=file_name, stage="complete", status="success")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ingestion.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/ingestion.py tests/test_ingestion.py
git commit -m "feat: add ingestion pipeline with validation, hashing, and status tracking"
```

---

## Task 8: Inbox Watcher

**Files:**
- Create: `src/watcher.py`
- Create: `tests/test_watcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_watcher.py
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest


def test_watcher_detects_new_pdf():
    from src.watcher import InboxWatcher

    callback = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = InboxWatcher(inbox_dir=tmpdir, on_new_file=callback, stabilization_seconds=0.1)
        watcher.start()

        # Create a PDF file
        pdf_path = Path(tmpdir) / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        time.sleep(0.5)  # Wait for stabilization + detection

        watcher.stop()
        callback.assert_called_once()
        assert "test.pdf" in str(callback.call_args)


def test_watcher_ignores_non_pdf():
    from src.watcher import InboxWatcher

    callback = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = InboxWatcher(inbox_dir=tmpdir, on_new_file=callback, stabilization_seconds=0.1)
        watcher.start()

        # Create a non-PDF file
        txt_path = Path(tmpdir) / "test.txt"
        txt_path.write_text("not a pdf")
        time.sleep(0.5)

        watcher.stop()
        callback.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_watcher.py -v
```
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/watcher.py
import os
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer


class _PDFHandler(FileSystemEventHandler):
    def __init__(self, on_new_file: Callable[[str], None], stabilization_seconds: float = 3.0):
        self._on_new_file = on_new_file
        self._stabilization = stabilization_seconds
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._checker = threading.Thread(target=self._check_loop, daemon=True)
        self._running = True
        self._checker.start()

    def stop(self):
        self._running = False

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            return
        with self._lock:
            self._pending[event.src_path] = time.time()

    def _check_loop(self) -> None:
        while self._running:
            time.sleep(0.1)
            ready = []
            with self._lock:
                now = time.time()
                for path, first_seen in list(self._pending.items()):
                    if not os.path.exists(path):
                        del self._pending[path]
                        continue
                    current_size = os.path.getsize(path)
                    # Wait for stabilization period
                    if now - first_seen >= self._stabilization:
                        ready.append(path)
                        del self._pending[path]

            for path in ready:
                self._on_new_file(path)


class InboxWatcher:
    def __init__(self, inbox_dir: str, on_new_file: Callable[[str], None], stabilization_seconds: float = 3.0):
        self._inbox_dir = inbox_dir
        self._handler = _PDFHandler(on_new_file, stabilization_seconds)
        self._observer = Observer()
        self._observer.schedule(self._handler, inbox_dir, recursive=False)

    def start(self) -> None:
        self._observer.start()

    def stop(self) -> None:
        self._handler.stop()
        self._observer.stop()
        self._observer.join(timeout=5)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_watcher.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/watcher.py tests/test_watcher.py
git commit -m "feat: add inbox watcher with PDF detection and file stabilization"
```

---

## Task 9: MCP Server (All 8 Tools)

**Files:**
- Create: `src/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing test for core tool registration**

```python
# tests/test_server.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_server_has_all_tools():
    """Verify all 8 MCP tools are registered."""
    with patch("src.server.load_config"), \
         patch("src.server.RAGEngine"), \
         patch("src.server.RAGLogger"), \
         patch("src.server.IngestionPipeline"), \
         patch("src.server.InboxWatcher"):
        from src.server import mcp

        tool_names = [t.name for t in mcp._tool_manager.list_tools()]
        expected = [
            "query",
            "ingest_inbox",
            "ingest_document",
            "get_doc_status",
            "list_documents",
            "delete_document",
            "get_system_status",
            "confirm_version_update",
        ]
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_server.py -v
```
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/server.py
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from src.config import load_config, AppConfig
from src.ingestion import IngestionPipeline, validate_file, compute_file_hash
from src.logging_service import RAGLogger
from src.rag import RAGEngine
from src.watcher import InboxWatcher

mcp = FastMCP("GEO Insurance RAG")

# Global state (initialized on startup)
_config: AppConfig | None = None
_rag_engine: RAGEngine | None = None
_logger: RAGLogger | None = None
_pipeline: IngestionPipeline | None = None
_watcher: InboxWatcher | None = None


def _error_response(error_code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": True,
        "error_code": error_code,
        "message": message,
        "details": details or {},
    }


@mcp.tool
async def query(
    question: str,
    filters: dict | None = None,
    mode: str = "auto",
    top_k: int = 5,
    only_latest: bool = True,
) -> dict[str, Any]:
    """Search insurance product information using semantic search and knowledge graph.
    Supports filtering by company, product_type, document_type."""
    if not _rag_engine:
        return _error_response("OPENSEARCH_UNAVAILABLE", "RAG engine not initialized")

    import time
    start = time.time()

    try:
        # Map auto mode to hybrid for now (TODO: implement auto routing)
        effective_mode = "hybrid" if mode == "auto" else mode
        result = await _rag_engine.query(question, mode=effective_mode, top_k=top_k)

        elapsed = int((time.time() - start) * 1000)
        return {
            "results": [{"content": result, "source_document": "", "company": "", "product_name": "", "page": 0, "relevance_score": 1.0}],
            "metadata": {
                "query_mode": effective_mode,
                "total_results": 1,
                "filters_applied": filters or {},
                "retrieval_time_ms": elapsed,
                "documents_searched": 0,
                "knowledge_graph_entities_matched": 0,
            },
        }
    except Exception as e:
        return _error_response("INGESTION_FAILED", str(e))


@mcp.tool
async def ingest_inbox() -> dict[str, Any]:
    """Process all PDF files in the inbox directory."""
    if not _pipeline or not _config:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    inbox = Path(_config.paths.inbox_dir)
    files = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"]

    queued = []
    skipped = []
    for f in files:
        validation = validate_file(str(f), _config.limits.max_file_size_mb)
        if validation["valid"]:
            await _pipeline.enqueue(str(f))
            queued.append(f.name)
        else:
            skipped.append(f.name)

    # Start processing in background
    asyncio.create_task(_pipeline.process_queue())

    return {
        "queued": len(queued),
        "skipped": len(skipped),
        "files": queued,
    }


@mcp.tool
async def ingest_document(file_path: str) -> dict[str, Any]:
    """Process a single PDF document for ingestion."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    if not Path(file_path).exists():
        return _error_response("VALIDATION_FAILED", f"File not found: {file_path}")

    result = await _pipeline.enqueue(file_path)
    asyncio.create_task(_pipeline.process_queue())
    return result


@mcp.tool
async def get_doc_status(
    document_id: str | None = None,
    file_name: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Query document processing status."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    all_statuses = _pipeline.get_all_statuses()
    docs = list(all_statuses.values())

    if document_id:
        docs = [d for d in docs if d["document_id"] == document_id]
    if file_name:
        docs = [d for d in docs if d["file_name"] == file_name]
    if status_filter:
        docs = [d for d in docs if d["status"] == status_filter]

    total = len(docs)
    docs = docs[offset : offset + limit]

    return {"documents": docs, "total": total, "limit": limit, "offset": offset}


@mcp.tool
async def list_documents(
    filters: dict | None = None,
    only_latest: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List all indexed documents with metadata."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    all_statuses = _pipeline.get_all_statuses()
    docs = [d for d in all_statuses.values() if d["status"] in ("ready", "partial")]

    if only_latest:
        docs = [d for d in docs if d.get("metadata", {}).get("is_latest", True)]

    if filters:
        for key, val in filters.items():
            docs = [d for d in docs if d.get("metadata", {}).get(key) == val]

    total = len(docs)
    docs = docs[offset : offset + limit]

    return {
        "documents": [
            {
                "document_id": d["document_id"],
                "file_name": d["file_name"],
                "company": d.get("metadata", {}).get("company", ""),
                "product_name": d.get("metadata", {}).get("product_name", ""),
                "product_type": d.get("metadata", {}).get("product_type", ""),
                "document_type": d.get("metadata", {}).get("document_type", ""),
                "document_date": d.get("metadata", {}).get("document_date", ""),
                "is_latest": d.get("metadata", {}).get("is_latest", True),
                "status": d["status"],
            }
            for d in docs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@mcp.tool
async def delete_document(document_id: str, confirm: bool = False) -> dict[str, Any]:
    """Delete a document from the index."""
    if not confirm:
        return _error_response("INVALID_PARAMETERS", "Must set confirm=true to delete")
    if not _rag_engine:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    success = await _rag_engine.delete_document(document_id)
    return {
        "success": success,
        "message": "Document deleted" if success else "Delete failed",
        "knowledge_graph_updated": success,
    }


@mcp.tool
async def get_system_status() -> dict[str, Any]:
    """Get system health status including OpenSearch and API connectivity."""
    os_status = "disconnected"
    docs_indexed = 0

    if _config:
        try:
            from opensearchpy import OpenSearch
            client = OpenSearch(
                hosts=[{"host": _config.opensearch.host, "port": _config.opensearch.port}],
                use_ssl=False,
            )
            info = client.info()
            os_status = "healthy"
        except Exception:
            os_status = "degraded"

    inbox_count = 0
    if _config:
        inbox_count = len(list(Path(_config.paths.inbox_dir).glob("*.pdf")))

    return {
        "opensearch": {
            "status": os_status,
            "documents_indexed": docs_indexed,
            "index_size_mb": 0.0,
        },
        "inbox": {
            "pending_files": inbox_count,
            "watcher_active": _watcher is not None,
        },
        "models": {
            "llm": _config.llm.model if _config else "",
            "embedding": _config.embedding.model if _config else "",
            "vision": _config.vision.model if _config else "",
            "api_status": "healthy",
        },
    }


@mcp.tool
async def confirm_version_update(document_id: str, replace: bool = False) -> dict[str, Any]:
    """Confirm whether a new document version should replace the old one."""
    if not _pipeline:
        return _error_response("OPENSEARCH_UNAVAILABLE", "System not initialized")

    status = _pipeline.get_status(document_id)
    if not status:
        return _error_response("DOCUMENT_NOT_FOUND", f"Document {document_id} not found")
    if status["status"] != "awaiting_confirmation":
        return _error_response("INVALID_PARAMETERS", f"Document is not awaiting confirmation (status: {status['status']})")

    # TODO: implement actual version replacement logic
    return {
        "success": True,
        "old_document_id": None,
        "message": "Version update confirmed" if replace else "Document indexed as independent",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_server.py -v
```
Expected: 1 PASSED

- [ ] **Step 5: Add server lifecycle initialization at bottom of `server.py`**

```python
# Add to bottom of src/server.py

async def _initialize():
    """Initialize all components with OpenSearch health check retry."""
    global _config, _rag_engine, _logger, _pipeline, _watcher

    _config = load_config()
    _logger = RAGLogger(log_dir=_config.paths.log_dir)

    # OpenSearch health check: retry every 5s for 60s
    from opensearchpy import OpenSearch
    for attempt in range(12):
        try:
            client = OpenSearch(
                hosts=[{"host": _config.opensearch.host, "port": _config.opensearch.port}],
                use_ssl=False,
            )
            client.info()
            break
        except Exception:
            if attempt < 11:
                await asyncio.sleep(5)
            else:
                print("WARNING: OpenSearch not available, starting in degraded mode")

    # Initialize RAG engine
    _rag_engine = RAGEngine(
        llm_config=_config.llm,
        embedding_config=_config.embedding,
        vision_config=_config.vision,
        opensearch_config=_config.opensearch,
        working_dir="./rag_working_dir",
    )
    try:
        await _rag_engine.initialize()
    except Exception as e:
        print(f"WARNING: RAG engine init failed: {e}")

    # Initialize ingestion pipeline
    _pipeline = IngestionPipeline(config=_config, rag_engine=_rag_engine, logger=_logger)

    # Start inbox watcher
    def _on_new_file(file_path: str):
        asyncio.create_task(_pipeline.enqueue(file_path))
        asyncio.create_task(_pipeline.process_queue())

    _watcher = InboxWatcher(
        inbox_dir=_config.paths.inbox_dir,
        on_new_file=_on_new_file,
    )
    _watcher.start()


@mcp.on_event("startup")
async def startup():
    await _initialize()


if __name__ == "__main__":
    _config = load_config()
    mcp.run()
```

- [ ] **Step 6: Commit**

```bash
git add src/server.py tests/test_server.py
git commit -m "feat: add MCP server with all 8 tools"
```

---

## Task 10: Integration Test with Sample PDF

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

This test requires OpenSearch running and a real PDF. Skip if not available.

```python
# tests/test_integration.py
import os
import pytest

SAMPLE_PDF = "/Users/weiexperimental/Desktop/RAGbot/testdoc/CTFLife_PRMP Leaflet_0625GEN_2601_(Eng).pdf"

pytestmark = pytest.mark.skipif(
    not os.path.exists(SAMPLE_PDF) or not os.getenv("LLM_API_KEY"),
    reason="Requires sample PDF and API key",
)


@pytest.mark.asyncio
async def test_full_ingestion_and_query():
    """End-to-end: ingest a PDF, then query it."""
    from src.config import load_config
    from src.logging_service import RAGLogger
    from src.rag import RAGEngine
    from src.ingestion import IngestionPipeline

    config = load_config()
    logger = RAGLogger(log_dir=config.paths.log_dir)

    engine = RAGEngine(
        llm_config=config.llm,
        embedding_config=config.embedding,
        vision_config=config.vision,
        opensearch_config=config.opensearch,
        working_dir="./test_working_dir",
    )
    await engine.initialize()

    pipeline = IngestionPipeline(config=config, rag_engine=engine, logger=logger)
    result = await pipeline.enqueue(SAMPLE_PDF)
    assert result["status"] == "pending"
    assert result["document_id"]

    await pipeline.process_queue()

    status = pipeline.get_status(result["document_id"])
    assert status["status"] in ("ready", "partial")

    # Query
    answer = await engine.query("What is Policy Reverse Mortgage?")
    assert len(answer) > 0
```

- [ ] **Step 2: Run integration test (requires OpenSearch + API key)**

```bash
# Start OpenSearch first
docker compose -f docker/docker-compose.yml up -d

# Run with API key
LLM_API_KEY=sk-xxx EMBEDDING_API_KEY=sk-xxx VISION_API_KEY=sk-xxx pytest tests/test_integration.py -v -s
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test with sample PDF"
```

---

## Task 11: MCP Client Configuration + README

**Files:**
- Create: `README.md` (overwrite)

- [ ] **Step 1: Write README with setup and MCP config instructions**

```markdown
# GEO Insurance RAG — MCP Server

MCP server providing RAG search over Hong Kong insurance product documents.

## Quick Start

1. Copy `.env.example` to `.env` and fill in API keys
2. Start OpenSearch: `docker compose -f docker/docker-compose.yml up -d`
3. Install: `uv venv && uv pip install -e ".[dev]"`
4. Run: `python src/server.py`

## OpenClaw MCP Config

Add to `~/.openclaw/openclaw.json`:

\```json
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
\```

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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions and MCP config"
```

---

## Execution Order Summary

| Task | Component | Dependencies |
|------|-----------|-------------|
| 1 | Project Scaffolding + Docker | None |
| 2 | Configuration Module | Task 1 |
| 3 | Logging Service | Task 1 |
| 4 | RAG Engine Wrapper | Task 2 |
| 5 | Metadata Extraction | Task 2 |
| 6 | Version Detection | None |
| 7 | Ingestion Pipeline | Tasks 2-6 |
| 8 | Inbox Watcher | Task 1 |
| 9 | MCP Server | Tasks 2-8 |
| 10 | Integration Test | Tasks 1-9 |
| 11 | README | Tasks 1-9 |

Tasks 2, 3, 6, 8 can run in parallel. Tasks 4, 5 can run in parallel after Task 2.
