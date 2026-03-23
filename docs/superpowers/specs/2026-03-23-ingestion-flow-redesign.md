# Ingestion Flow Redesign — 去 Hook、去 Watchdog、直接入庫

**日期：** 2026-03-23
**狀態：** Draft (Rev 2 — 修正 spec review issues)

---

## 背景

原本嘅 MCP server 設計喺加入 OpenClaw 之後出現多個架構問題：

1. **Watchdog 失效** — MCP server 係 acpx lazy spawn（stdio transport），server 唔跑嗰陣 watchdog 唔存在
2. **Hook fire-and-forget** — `message:preprocessed` hook 唔會被 await，agent 可能喺 hook 完成前已經開始處理
3. **In-memory state 唔持久** — `_doc_statuses` 同 `_known_hashes` 喺 server restart 後丟失
4. **多觸發源衝突** — watchdog、agent call、heartbeat 三者可能同時觸發同一份文件入庫

## 設計目標

- 消除所有 race condition
- 每個入庫場景有獨立、清晰嘅觸發路徑
- State 跨 server restart 持久化
- 最少改動量

---

## 核心發現

### 1. Katrina 可以直接攞到文件路徑

Agent 收到 WhatsApp 附件時見到：
```
[media attached: /Users/.../.openclaw/media/inbound/filename---uuid.pdf (application/pdf)]
```
包含完整 absolute path 同 MIME type。Agent 可以直接將 path 傳入 MCP tool。

### 2. MCP server 唔係每次 call 完就死

ACPX 嘅 Queue Owner 機制保持 agent + MCP server alive（預設 idle timeout 5 分鐘）。連續 tool call 期間 server 係長駐嘅。

### 3. Hook 嘅 `event.messages.push()` 冇效

`message:preprocessed` 係 fire-and-forget。push 嘅 messages 永遠唔會被讀取。Hook 唔能可靠咁同 agent 通訊。

---

## 新設計

### 架構概覽

```
WhatsApp PDF:
  Agent 見到 [media attached: /path/to/file.pdf]
  → call ingest_document(file_path="/path/to/file.pdf")
  → Pipeline 直接從原始路徑處理
  → 完成後 move 去 processed/

手動拉文件入 inbox:
  → Heartbeat check get_system_status → pending_files > 0
  → call ingest_inbox
  → Pipeline 處理 inbox 入面所有 PDF
```

### 移除嘅組件

| 組件 | 原因 |
|------|------|
| `pdf-to-inbox` hook | 唔需要，Katrina 直接用 media path |
| Watchdog (`watcher.py`) | 唔需要，heartbeat 取代偵測功能 |
| `server.py` 中 watcher 初始化 | 跟隨 watchdog 移除 |

### 保留嘅組件

| 組件 | 用途 |
|------|------|
| `ingest_document(path)` | WhatsApp 上傳入口 |
| `ingest_inbox()` | 手動拉文件 + heartbeat 入口 |
| `data/inbox/` 目錄 | 手動拉文件用 |
| `data/processed/` 目錄 | 成功入庫嘅文件 |
| `data/failed/` 目錄 | 入庫失敗嘅文件 |

---

## Code 改動

### 改動 1：`ingestion.py` — file path dedup

**問題：** 同一份文件可能被 enqueue 多次（heartbeat 撞車、agent 重複 call）。

**方案：** `enqueue()` 前 check file path。用 O(1) lookup dict 而唔係 linear scan。

> **注意：** Path dedup 只係 fast-path optimization，防止「heartbeat call `ingest_inbox` 兩次」嘅情況。
> Hash dedup（喺 `_process_single` 入面）仍然係 authoritative 嘅重複檢查，覆蓋唔同路徑但相同內容嘅情況。

```python
class IngestionPipeline:
    def __init__(self, ...):
        # ... existing fields ...
        self._path_to_doc_id: dict[str, str] = {}  # O(1) path lookup

    async def enqueue(self, file_path: str) -> dict[str, Any]:
        # Fast-path dedup: 同一個 path 唔使重複 enqueue
        if file_path in self._path_to_doc_id:
            existing_id = self._path_to_doc_id[file_path]
            existing = self._doc_statuses.get(existing_id)
            if existing and existing["status"] not in ("failed",):
                return {
                    "document_id": existing_id,
                    "status": existing["status"],
                    "duplicate": True,
                }

        # 正常 enqueue
        doc_id = str(uuid.uuid4())
        self._path_to_doc_id[file_path] = doc_id
        # ... 其餘不變
```

`failed` 狀態嘅文件允許重新 enqueue（retry）。

### 改動 2：`ingestion.py` — persist state 去 OpenSearch

**問題：** `_doc_statuses` 同 `_known_hashes` 喺 memory，server restart 後丟失。

**方案：** 用 OpenSearch `rag-ingestion-status` index 儲存。

```python
class IngestionPipeline:
    def __init__(self, config, rag_engine, logger, opensearch_client=None):
        self._os_client = opensearch_client
        self._doc_statuses: dict[str, dict] = {}
        self._known_hashes: set[str] = set()
        # Startup: load existing statuses from OpenSearch
        if self._os_client:
            self._load_persisted_state()

    def _load_persisted_state(self):
        """從 OpenSearch 恢復 state。"""
        try:
            resp = self._os_client.search(
                index="rag-ingestion-status",
                body={"query": {"match_all": {}}, "size": 10000}
            )
            for hit in resp["hits"]["hits"]:
                doc = hit["_source"]
                self._doc_statuses[doc["document_id"]] = doc
                if doc.get("file_hash"):
                    self._known_hashes.add(doc["file_hash"])
        except Exception:
            pass  # Index 可能未存在，繼續

    _persist_failures: int = 0

    def _persist_status(self, doc_id: str):
        """將單個 doc status 寫入 OpenSearch。Best-effort，唔影響主流程但會 log 錯誤。"""
        if not self._os_client:
            return
        try:
            self._os_client.index(
                index="rag-ingestion-status",
                id=doc_id,
                body=self._doc_statuses[doc_id],
            )
        except Exception as e:
            self._persist_failures += 1
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to persist status for {doc_id}: {e} "
                f"(total failures: {self._persist_failures})"
            )
```

每次 status 變化時 call `_persist_status(doc_id)`。
`get_system_status` 會 surface `_persist_failures` count，方便 monitoring。

#### OpenSearch Index 初始化

`_initialize()` 時建立 index template，確保 mapping 正確：

```python
async def _ensure_ingestion_index(client):
    """確保 rag-ingestion-status index 存在，mapping 正確。"""
    if not client.indices.exists("rag-ingestion-status"):
        client.indices.create("rag-ingestion-status", body={
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "file_name": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "file_hash": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "ingested_at": {"type": "date"},
                    "metadata": {"type": "object", "dynamic": True},
                    "stages": {"type": "nested"},
                }
            }
        })
```

### 改動 3：`ingestion.py` — startup recovery

**問題：** Server crash 喺 processing 中途，文件變孤兒。

**方案：** 獨立嘅 `async def recover_crashed()` method，由 `server.py` 嘅 `_initialize()` 喺建構 pipeline 之後顯式 `await`。

> **注意：** 唔好喺 `__init__` 或 `_load_persisted_state` 入面用 `asyncio.get_event_loop().call_soon()` — 呢個喺 sync context 入面係 unsafe 嘅。

```python
async def recover_crashed(self):
    """檢查 OpenSearch 入面有冇 crash 前未完成嘅文件，重新 enqueue。"""
    recovered = []
    for doc_id, status in list(self._doc_statuses.items()):
        if status["status"] in ("parsing", "extracting_metadata", "checking_version", "validating"):
            file_path = status["file_path"]
            if Path(file_path).exists():
                status["status"] = "pending"
                self._persist_status(doc_id)  # 即時 persist 新狀態
                await self._queue.put((doc_id, file_path))
                recovered.append(file_path)
            else:
                # 文件已經唔在，標記為 failed
                status["status"] = "failed"
                status["stages"].append({
                    "stage": "recovery", "status": "failed",
                    "duration_ms": 0, "error": "File not found after crash"
                })
                self._persist_status(doc_id)

    if recovered:
        asyncio.create_task(self.process_queue())

    return recovered
```

`server.py` 嘅 `_initialize()` 中：
```python
_pipeline = IngestionPipeline(config=_config, ...)
recovered = await _pipeline.recover_crashed()
if recovered:
    print(f"Recovered {len(recovered)} crashed documents")
```

### 改動 4：`server.py` — 移除 watchdog + 共享 OpenSearch client

```python
# 刪除:
from src.watcher import InboxWatcher

# 刪除 global:
_watcher: InboxWatcher | None = None

# 新增 global（共享 client，get_system_status 亦用）:
_os_client: OpenSearch | None = None

# 刪除 lifespan 中:
if _watcher:
    _watcher.stop()

# 刪除 _initialize() 中嘅 watcher 相關 code

# 修改 _initialize():
global _os_client
_os_client = OpenSearch(
    hosts=[{"host": _config.opensearch.host, "port": _config.opensearch.port}],
    use_ssl=False,
)
await _ensure_ingestion_index(_os_client)  # 確保 index 存在
_pipeline = IngestionPipeline(
    config=_config,
    rag_engine=_rag_engine,
    logger=_logger,
    opensearch_client=_os_client,
)
recovered = await _pipeline.recover_crashed()
```

`get_system_status` 改用共享 `_os_client` 而唔係每次建立新 client。

### 改動 5：`server.py` — `get_system_status` 修正

確保 `pending_files` count 排除已經喺 pipeline 中嘅文件。同時：
- 用共享 `_os_client` 而唔係每次建新 client
- 移除 `watcher_active` field
- 新增 `persist_failures` field

```python
@mcp.tool
async def get_system_status() -> dict[str, Any]:
    os_status = "disconnected"
    if _os_client:
        try:
            _os_client.info()
            os_status = "healthy"
        except Exception:
            os_status = "degraded"

    inbox_count = 0
    if _config:
        all_inbox = set(str(f) for f in Path(_config.paths.inbox_dir).glob("*.pdf"))
        tracked = set(s["file_path"] for s in _pipeline.get_all_statuses().values()
                      if s["status"] not in ("failed",))
        inbox_count = len(all_inbox - tracked)

    return {
        "opensearch": {"status": os_status, ...},
        "inbox": {
            "pending_files": inbox_count,
            "heartbeat_inbox_check": True,  # 取代 watcher_active
        },
        "persistence": {
            "failures": _pipeline._persist_failures if _pipeline else 0,
        },
        "models": {...},
    }
```

### 改動 6：`server.py` — `ingest_inbox` 移除 pre-validation

而家 `ingest_inbox` 先 `validate_file` 再 `enqueue`，但 `_process_single` 入面又 validate 一次。
問題：pre-validation 失敗嘅文件唔會入 `_doc_statuses`，heartbeat 每次都會重試。

改為：所有 validation 由 pipeline 負責，`ingest_inbox` 只負責 enqueue。

```python
@mcp.tool
async def ingest_inbox() -> dict[str, Any]:
    inbox = Path(_config.paths.inbox_dir)
    files = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"]

    queued = []
    skipped = []
    for f in files:
        result = await _pipeline.enqueue(str(f))
        if result.get("duplicate"):
            skipped.append(f.name)
        else:
            queued.append(f.name)

    if queued:
        asyncio.create_task(_pipeline.process_queue())

    return {"queued": len(queued), "skipped": len(skipped), "files": queued}
```

---

## OpenClaw 配置改動

### AGENTS.md — 文件上傳流程

```markdown
## 文件上傳流程

當你收到 PDF 附件，你會見到類似：
[media attached: /Users/.../.openclaw/media/inbound/filename.pdf (application/pdf)]

**流程：**
1. 回覆用戶：「收到 [文件名]，正在處理入庫...」
2. 從 [media attached: ...] 提取完整 file path
3. Call `ingest_document(file_path="提取到嘅完整路徑")`
4. Call `get_doc_status` 查詢結果
5. 回報結果

**非 PDF 文件：** 回覆「我只支援 PDF 格式嘅文件入庫」
```

### HEARTBEAT.md — 新增 inbox 檢查

```markdown
### 1. Inbox 檢查
Call `get_system_status`：
- pending_files > 0 → call `ingest_inbox` 觸發入庫
- pending_files = 0 → skip

### 2. 入庫狀態
Call `get_doc_status` 檢查有無新變化
- 有新結果 → 通知用戶
- 冇變化 → skip
```

### TOOLS.md — 移除 watchdog 描述

移除「watchdog 監察中」嘅描述。更新為：
- WhatsApp 上傳：Katrina 直接 call `ingest_document`
- 手動拉文件：放入 `data/inbox/`，heartbeat 會自動處理

### Hook — 移除 `pdf-to-inbox`

```bash
openclaw hooks disable pdf-to-inbox
rm -rf ~/.openclaw/hooks/pdf-to-inbox/
```

---

## Edge Cases

### 同一份文件 send 兩次
- 第二次 `enqueue()` → hash dedup → return `duplicate: true`
- 如果 server 中間 restart 過：OpenSearch 有 hash record → 仍然 dedup

### 大文件手動拉入 inbox 中途被 heartbeat 掃到
- 概率低（本地 copy 幾乎即時）
- 最壞情況：MinerU parse 失敗 → 搬去 `failed/` → 用戶需要重新拉入
- 可選改進：`ingest_inbox` 加 file size stabilization check（比較 size 前後 1 秒有冇變化）

### Server crash 喺 processing 中途
- OpenSearch 有 `parsing` 狀態嘅 record
- Server restart → `_load_persisted_state()` 偵測到 → 檢查文件仲在唔在 → re-enqueue
- 如果文件已經被移走（e.g. MinerU 部分完成）→ skip，狀態保持 `failed`

### Heartbeat 同 WhatsApp call 同時觸發
- `enqueue()` file path dedup 保證同一份文件唔會重複
- `process_queue()` 有 `_lock` 保證順序處理

---

## 測試計劃

| 場景 | 測試方法 |
|------|---------|
| WhatsApp 上傳 → 成功入庫 | Send PDF via WhatsApp，驗證 processed/ 有文件 |
| 手動拉文件 → heartbeat 入庫 | 放 PDF 入 inbox，等 heartbeat，驗證結果 |
| 重複文件 dedup | Send 同一份 PDF 兩次，第二次應 return duplicate |
| Server restart recovery | Kill MCP server 喺 parsing 中途，重啟後確認 re-process |
| File path dedup | 連續 call ingest_inbox 兩次，確認唔會重複 enqueue |
| State persistence | 入庫成功後 restart server，call get_doc_status 確認 state 存在 |

---

## 測試計劃（補充）

除咗 integration tests，需要新增 unit tests：

| 測試 | 覆蓋 |
|------|------|
| `test_enqueue_path_dedup` | 同一 path enqueue 兩次，第二次 return duplicate |
| `test_enqueue_failed_retry` | failed 狀態嘅 path 可以重新 enqueue |
| `test_persist_status_success` | Status 變化後 OpenSearch 有對應 record |
| `test_persist_status_failure` | OpenSearch down 時 `_persist_failures` 遞增，pipeline 繼續運作 |
| `test_load_persisted_state` | Mock OpenSearch response，驗證 state 恢復 |
| `test_recover_crashed_file_exists` | Crash recovery 搵到文件 → re-enqueue |
| `test_recover_crashed_file_gone` | Crash recovery 文件唔在 → mark failed |
| `test_ingest_inbox_no_prevalidation` | ingest_inbox 唔做 validation，交畀 pipeline |

---

## 改動摘要

| 文件 | 改動 |
|------|------|
| `src/ingestion.py` | File path dedup (O(1) dict)、OpenSearch persist (with logging)、startup recovery (async method)、index init |
| `src/server.py` | 移除 watchdog、共享 OpenSearch client、修正 get_system_status、ingest_inbox 移除 pre-validation |
| `CLAUDE.md` | 移除 watchdog 出技術棧、更新 OpenSearch port 為 9200 |
| `openclaw/katrina/AGENTS.md` | 新文件上傳流程（用 media path，唔再提 hook） |
| `openclaw/katrina/HEARTBEAT.md` | 加 inbox 檢查（get_system_status → ingest_inbox） |
| `openclaw/katrina/TOOLS.md` | 移除 watchdog 描述、更新上傳流程描述 |
| `~/.openclaw/hooks/pdf-to-inbox/` | 移除 |
| `src/watcher.py` | 保留唔刪（唔使喺 server 入面），將來可能有用 |
| `tests/test_ingestion.py` | 新增 8 個 unit tests（dedup、persist、recovery） |
