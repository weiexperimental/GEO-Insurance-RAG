# HEARTBEAT.md - Katrina 定期任務

你必須按以下步驟執行，唔好跳過。

## 定期 Heartbeat（每 5 分鐘）

### Step 1: 檢查系統狀態
Call `get_system_status` tool。

### Step 2: 決定行動

**情況 A — inbox 有新文件：** `inbox.pending_files > 0`
→ 通知用戶：「開始入庫 [pending_files] 份文件」
→ **你必須立即 call `ingest_all` tool**（唔好跳過，呢個係實際觸發入庫嘅動作）
→ 等 `ingest_all` 返回結果後，通知用戶結果
→ Reply HEARTBEAT_OK

**情況 B — 冇新文件：** `inbox.pending_files == 0`
→ Reply HEARTBEAT_OK（靜音）

---

## 回調處理（收到 [入庫回調] 訊息時）

當你收到以 `[入庫回調]` 開頭嘅訊息：

### Step 1: 查詢入庫結果
從訊息提取 `document_id`，call `list_documents` 查狀態。

### Step 2: 通知用戶
- 成功：「✅ [file_name] 入庫成功。公司：[company] 產品：[product_name]」
- 失敗：「❌ [file_name] 入庫失敗」

### Step 3: 檢查 inbox
Call `get_system_status`，如果 `inbox.pending_files > 0` 通知用戶仲有文件等緊。
