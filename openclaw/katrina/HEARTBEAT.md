# HEARTBEAT.md - Katrina 定期任務

## 每次 heartbeat 檢查以下項目：

### 1. Inbox 新文件
Call `get_system_status`：
- **pending_files > 0** → call `ingest_inbox` 觸發入庫
- **pending_files = 0** → skip

### 2. 入庫狀態
Call `get_doc_status` 檢查有無新變化：
- **ready** → 通知用戶：「[文件名] 已成功入庫，識別到係 [公司] 嘅 [產品名稱]」
- **failed** → 警告用戶：「[文件名] 入庫失敗：[error]」
- **partial** → 通知用戶：「[文件名] 已入庫但 metadata 唔完整」
- **awaiting_confirmation** → 提醒用戶確認版本更新
- 冇新變化 → 唔使講嘢

### 3. 系統健康
Call `get_system_status` 快速檢查：
- OpenSearch 斷線 → 立即通知用戶
- persist_failures > 0 → 警告用戶「狀態持久化有問題」
- 其他正常 → 唔使講嘢

### 規則
- 只通知有變化嘅嘢，唔好重複報告已經講過嘅狀態
- 冇嘢要報 → reply HEARTBEAT_OK
- 深夜（23:00-08:00）只報 failed 同 system down，其他留到朝早
