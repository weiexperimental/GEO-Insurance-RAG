# Heartbeat-Driven Ingestion with Gateway Callback

## Problem

The current heartbeat + ingestion flow has several bugs:

1. **False "0 files" messages**: After `ingest_inbox` enqueues all files, they become tracked immediately. Next heartbeat sees `pending_files = 0` and reports "已開始入庫 0 份文件" — incorrect and noisy.
2. **No per-file progress**: Katrina only reports at the moment of enqueue, never during processing or on completion.
3. **Batch enqueue**: `ingest_inbox` enqueues ALL files at once. No way to report per-file progress.
4. **No completion details**: User never learns if ingestion succeeded, how long it took, or what was extracted.
5. **Heartbeat-bound**: Ingestion progress is only checked every 5 minutes. After one file finishes, the next one doesn't start until the next heartbeat.

## Solution: Gateway Callback Loop

Use OpenClaw's `/hooks/agent` webhook endpoint to create a callback-driven ingestion loop. The MCP server processes files in the background and POSTs to the gateway when each file completes, triggering a new Katrina turn that reports results and starts the next file.

## Architecture

```
Heartbeat (every 5m)
  → Katrina calls get_system_status
  → If pending_files > 0 AND processing_files = 0:
      → Call ingest_next (enqueues 1 file, returns immediately)
      → Notify user: "開始入庫 [filename]，inbox 仲有 [N] 份"
  → If processing_files > 0:
      → HEARTBEAT_OK (silent — ingestion in progress, wait for callback)
  → If both = 0:
      → Normal heartbeat (check doc_status for changes, else HEARTBEAT_OK)

MCP Server (background)
  → _process_single completes (ready / failed / partial / awaiting_confirmation)
  → POST /hooks/agent with completion message
  → Triggers new Katrina turn

Callback-triggered Katrina turn
  → Call get_doc_status(document_id=xxx) → get full results
  → Notify user: success/fail + time + details
  → Call get_system_status → still pending?
  → If yes: call ingest_next → notify user → wait for next callback
  → If no: "所有文件入庫完成"
```

**User queries are unaffected.** Ingestion runs in the MCP server's background asyncio task. User messages create new Katrina turns that can call `query` tool normally.

## Components

### 1. New MCP Tool: `ingest_next`

Replaces `ingest_inbox` for heartbeat use. Processes exactly one file at a time.

```python
@mcp.tool
async def ingest_next() -> dict[str, Any]:
    """Pick the next unprocessed PDF from inbox and start ingestion."""
    inbox = Path(_config.paths.inbox_dir)
    all_inbox = [f for f in inbox.iterdir() if f.suffix.lower() == ".pdf"]
    all_statuses = _pipeline.get_all_statuses()
    tracked = set(
        s["file_path"] for s in all_statuses.values()
        if s["status"] not in ("failed",)
    )

    pending = [f for f in all_inbox if str(f.resolve()) not in tracked]
    if not pending:
        return {"status": "empty", "remaining": 0}

    target = pending[0]
    result = await _pipeline.enqueue(str(target))
    if not result.get("duplicate"):
        asyncio.create_task(_pipeline.process_queue())

    return {
        "status": "started",
        "file_name": target.name,
        "document_id": result["document_id"],
        "remaining": len(pending) - 1,
    }
```

`ingest_inbox` is retained for manual batch use but heartbeat no longer calls it. **Mutual exclusion:** `ingest_inbox` should not be called while `processing_files > 0`. The tool should check and return an error if ingestion is already in progress.

**Concurrency note:** `ingest_next` relies on `process_queue()`'s `asyncio.Lock` to prevent concurrent processing. The lock must not be removed or weakened. The `pending` state is included in `processing_states`, so `get_system_status` correctly reports `processing_files > 0` even for files that have been enqueued but not yet started.

### 2. Gateway Callback in `_process_single`

After each file completes processing (any terminal state), POST to `/hooks/agent`:

```python
async def _notify_gateway(self, doc_id: str, status: dict):
    """Notify OpenClaw gateway that ingestion completed."""
    if not self._hooks_token:
        return  # Callback not configured, fall back to heartbeat

    import aiohttp
    url = f"http://127.0.0.1:{self._gateway_port}/hooks/agent"
    payload = {
        "message": (
            f"[入庫回調] {status['file_name']} 完成，狀態：{status['status']}，"
            f"document_id: {doc_id}。按 HEARTBEAT.md 嘅「回調處理」流程執行。"
        ),
        "deliver": True,
        "channel": "whatsapp",
        "to": self._notify_to,
    }
    headers = {"Authorization": f"Bearer {self._hooks_token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    _logger_mod.warning("Gateway callback failed: HTTP %d", resp.status)
    except Exception as e:
        _logger_mod.warning("Gateway callback error: %s", e)
```

Called at the end of `_process_single` for all terminal states: `ready`, `failed`, `partial`, `awaiting_confirmation`.

### 3. Enhanced `get_doc_status` Response

When a document reaches a terminal state, include ingestion statistics:

```python
# Added to each document in the response:
{
    "processing_time_ms": sum(s["duration_ms"] for s in status["stages"]),
    "stages_summary": [
        {"stage": s["stage"], "status": s["status"], "duration_ms": s["duration_ms"]}
        for s in status["stages"]
    ],
    # From metadata (if extracted):
    "company": metadata.get("company", ""),
    "product_name": metadata.get("product_name", ""),
    "product_type": metadata.get("product_type", ""),
}
```

### 4. Heartbeat Logic (HEARTBEAT.md)

Two modes: **heartbeat** (periodic check) and **callback** (triggered by MCP server on ingestion completion).

**Heartbeat mode (every 5 minutes):**

```markdown
Step 1: Call get_system_status. Check inbox section:
  - pending_files > 0 AND processing_files = 0:
    → Call ingest_next
    → Notify: "開始入庫 [file_name]，inbox 仲有 [remaining] 份"
  - processing_files > 0:
    → HEARTBEAT_OK (silent — wait for callback)
  - Both = 0:
    → Continue to Step 2

Step 2: Call get_doc_status (no params). Check for new completions:
  - ready → notify success with details
  - failed → warn with error
  - awaiting_confirmation → remind user

Step 3: If nothing to report → HEARTBEAT_OK
```

**Callback mode (triggered by `[入庫回調]` message):**

```markdown
When you receive a message starting with "[入庫回調]":
1. Extract document_id from the message
2. Call get_doc_status(document_id=xxx)
3. Report to user:
   - Success: "✅ [file_name] 入庫成功。公司：[company] 產品：[product_name] 耗時：[time]"
   - Failed: "❌ [file_name] 入庫失敗：[error]"
4. Call get_system_status → check pending_files
   - If pending_files > 0: Call ingest_next, notify: "開始入庫 [next_file]，仲有 [N] 份"
   - If pending_files = 0: "所有文件入庫完成。" then summarize total results
```

The callback message is minimal (file name, status, doc_id). All detailed logic lives in HEARTBEAT.md, not in the webhook payload. This avoids fragile prompt-engineering in the callback.

### 5. OpenClaw Config Changes

Enable webhook hooks in `~/.openclaw/openclaw.json`:

```json
{
  "hooks": {
    "enabled": true,
    "token": "<generated-secret>",
    "path": "/hooks",
    "internal": { "enabled": true, "entries": {} }
  }
}
```

**Authentication:** The `/hooks/agent` endpoint uses the `hooks.token` field, which is separate from `gateway.auth.token`. Both tokens must be configured. The MCP server uses `hooks.token` (via `OPENCLAW_HOOKS_TOKEN` env var) in the `Authorization: Bearer` header.

**Pre-implementation verification:** Before implementing the callback, manually verify the endpoint works:
```bash
# 1. Enable hooks in openclaw.json (add hooks.enabled + hooks.token)
# 2. Restart gateway
# 3. Test with curl:
curl -X POST http://127.0.0.1:18789/hooks/agent \
  -H "Authorization: Bearer <hooks-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test callback", "deliver": true, "channel": "whatsapp", "to": "+17807093869"}'
# Expected: Katrina receives and responds to "Test callback" via WhatsApp
```

This verification is **required** before proceeding with implementation. If the endpoint does not trigger a Katrina turn as expected, the fallback is to use heartbeat-only mode (the design degrades gracefully).

### 6. Plugin Tool Registration

Add `ingest_next` to the static `DEFAULT_TOOLS` array in `index.ts`:

```typescript
{
  name: "ingest_next",
  description: "Pick the next unprocessed PDF from inbox and start ingestion. Returns file name, document ID, and remaining count.",
  inputSchema: { type: "object", properties: {} },
}
```

## Config

New environment variables in `.env`:

```
OPENCLAW_HOOKS_TOKEN=<same token as openclaw.json hooks.token>
OPENCLAW_GATEWAY_PORT=18789       # default
OPENCLAW_NOTIFY_TO=+17807093869   # WhatsApp number for notifications
```

These are read by `IngestionPipeline.__init__()` and passed to `_notify_gateway()`.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Gateway callback POST fails | Log warning, don't block. Next heartbeat picks up completion. |
| Callback succeeds but Katrina turn fails | Same — heartbeat fallback. |
| MCP server crashes mid-ingestion | `recover_crashed()` re-enqueues on restart. Heartbeat triggers continue. |
| Bad PDF in inbox | Validation fails → moved to failed/ → callback notifies failure → next file starts. |
| Gateway token wrong (401) | Log error, degrade to heartbeat-only mode. |
| `aiohttp` not installed | Import error caught, callback disabled, heartbeat-only mode. |

**Fallback principle:** The callback is best-effort. If any part fails, the 5-minute heartbeat still works as before. The system never gets stuck.

## File Changes

| File | Change |
|------|--------|
| `src/ingestion.py` | Add `_notify_gateway()`, call at end of `_process_single` |
| `src/server.py` | New tool `ingest_next`, enhance `get_doc_status` response |
| `src/config.py` | Add `gateway_port`, `hooks_token`, `notify_to` fields |
| `.env.example` | Add `OPENCLAW_HOOKS_TOKEN`, `OPENCLAW_GATEWAY_PORT`, `OPENCLAW_NOTIFY_TO` |
| `~/.openclaw/openclaw.json` | Enable webhook hooks with token |
| `~/.openclaw/workspace/HEARTBEAT.md` | Rewrite with callback-aware logic |
| `~/.openclaw/extensions/insurance-rag/index.ts` | Add `ingest_next` tool definition |
| `tests/test_ingestion.py` | Test `ingest_next`, callback, heartbeat silence |

## Dependencies

- `aiohttp` — async HTTP client for gateway callback POST

**Init-time check:** `IngestionPipeline.__init__` should check for `aiohttp` availability once and set `self._callback_enabled = True/False`. This avoids catching import errors in the hot path of `_notify_gateway`.

```python
# In __init__:
try:
    import aiohttp
    self._callback_enabled = bool(hooks_token)
except ImportError:
    self._callback_enabled = False
    _logger_mod.warning("aiohttp not installed, gateway callbacks disabled")
```

## User Experience Flow

**16 files dropped into inbox:**

```
[Heartbeat fires]
Katrina: 開始入庫 BOCLife_2026開門紅.pdf，inbox 仲有 15 份

[~5 min later, callback fires]
Katrina: ✅ BOCLife_2026開門紅.pdf 入庫成功
         公司：中銀人壽  產品：2026開門紅（薪火2年保融）
         耗時：4 分 32 秒
         開始入庫 BOCLife_2026開門紅（薪火整付）.pdf，inbox 仲有 14 份

[User sends message during ingestion]
User: 智選儲蓄保嘅最低保費係幾多？
Katrina: 根據資料，智選儲蓄保嘅最低保費為... (normal query, unblocked)

[Callback fires]
Katrina: ✅ BOCLife_2026開門紅（薪火整付）.pdf 入庫成功
         ...
         開始入庫 CTFLife_HealthCare168.pdf，inbox 仲有 13 份

[... continues until inbox empty ...]

Katrina: 所有 16 份文件入庫完成。成功：14，失敗：2。
```
