# Ingestion Flow Redesign — 去 Hook、去 Watchdog、直接入庫

**日期：** 2026-03-23
**狀態：** Draft

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

**方案：** `enqueue()` 前 check file path 有冇已經喺 `_doc_statuses` 入面。

```python
async def enqueue(self, file_path: str) -> dict[str, Any]:
    # File path dedup: 如果已經 tracked 且唔係 failed，skip
    existing = next(
        (s for s in self._doc_statuses.values()
         if s["file_path"] == file_path and s["status"] not in ("failed",)),
        None
    )
    if existing:
        return {
            "document_id": existing["document_id"],
            "status": existing["status"],
            "duplicate": True,
        }

    # 正常 enqueue
    doc_id = str(uuid.uuid4())
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

    def _persist_status(self, doc_id: str):
        """將單個 doc status 寫入 OpenSearch。"""
        if not self._os_client:
            return
        try:
            self._os_client.index(
                index="rag-ingestion-status",
                id=doc_id,
                body=self._doc_statuses[doc_id],
            )
        except Exception:
            pass  # Best-effort，唔影響主流程
```

每次 status 變化時 call `_persist_status(doc_id)`。

### 改動 3：`ingestion.py` — startup recovery

**問題：** Server crash 喺 processing 中途，文件變孤兒。

**方案：** `_load_persisted_state()` 檢查 `parsing` / `extracting_metadata` 狀態嘅文件，reset 為 `pending` 重新 enqueue。

```python
def _load_persisted_state(self):
    # ... load from OpenSearch ...

    # Recovery: 搵出 crash 前未完成嘅文件
    for doc_id, status in self._doc_statuses.items():
        if status["status"] in ("parsing", "extracting_metadata", "checking_version", "validating"):
            file_path = status["file_path"]
            if Path(file_path).exists():
                status["status"] = "pending"
                # Re-enqueue for processing
                asyncio.get_event_loop().call_soon(
                    lambda did=doc_id, fp=file_path:
                        asyncio.create_task(self._re_enqueue(did, fp))
                )
```

只有原始文件仲存在先會 re-enqueue（如果已經搬咗去 processed/failed 就唔理）。

### 改動 4：`server.py` — 移除 watchdog

```python
# 刪除:
from src.watcher import InboxWatcher

# 刪除 global:
_watcher: InboxWatcher | None = None

# 刪除 lifespan 中:
if _watcher:
    _watcher.stop()

# 刪除 _initialize() 中:
def _on_new_file(file_path: str):
    asyncio.create_task(_pipeline.enqueue(file_path))
    asyncio.create_task(_pipeline.process_queue())

_watcher = InboxWatcher(...)
_watcher.start()

# 修改 _initialize():
# 加入 OpenSearch client 傳入 pipeline
from opensearchpy import OpenSearch
client = OpenSearch(hosts=[...], use_ssl=False)
_pipeline = IngestionPipeline(
    config=_config,
    rag_engine=_rag_engine,
    logger=_logger,
    opensearch_client=client,
)
```

### 改動 5：`server.py` — `get_system_status` 修正

確保 `pending_files` count 排除已經喺 pipeline 中嘅文件：

```python
# 而家：
inbox_count = len(list(Path(_config.paths.inbox_dir).glob("*.pdf")))

# 改為：
all_inbox = set(str(f) for f in Path(_config.paths.inbox_dir).glob("*.pdf"))
tracked = set(s["file_path"] for s in _pipeline.get_all_statuses().values()
              if s["status"] not in ("failed",))
inbox_count = len(all_inbox - tracked)
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

## 改動摘要

| 文件 | 改動 |
|------|------|
| `src/ingestion.py` | File path dedup、OpenSearch persist、startup recovery |
| `src/server.py` | 移除 watchdog、傳入 OpenSearch client |
| `openclaw/katrina/AGENTS.md` | 新文件上傳流程（用 media path） |
| `openclaw/katrina/HEARTBEAT.md` | 加 inbox 檢查 |
| `openclaw/katrina/TOOLS.md` | 移除 watchdog 描述 |
| `~/.openclaw/hooks/pdf-to-inbox/` | 移除 |
| `src/watcher.py` | 保留唔刪（唔使喺 server 入面），將來可能有用 |
