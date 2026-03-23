# OpenClaw Katrina 設定指南

呢份文檔記錄曬點樣喺一部新電腦上面 set up OpenClaw + Katrina agent + PDF 自動入庫 hook。

---

## 前置條件

- Node.js 已安裝
- Docker Desktop 已安裝並啟動
- OpenClaw 已安裝（`npm install -g openclaw`）
- OpenClaw 已完成初始設定（`openclaw setup`）
- WhatsApp 已對接好

---

## 目錄結構

```
openclaw/
├── SETUP.md              ← 你而家睇緊呢個
├── katrina/
│   ├── IDENTITY.md       ← Agent 身份
│   ├── SOUL.md           ← 性格、語氣、原則
│   ├── AGENTS.md         ← 運營規則、MCP tools 策略
│   ├── TOOLS.md          ← 環境配置
│   ├── HEARTBEAT.md      ← 定期任務
│   ├── USER.md           ← 用戶 profile
│   └── hooks/
│       └── pdf-to-inbox/
│           ├── HOOK.md      ← Hook metadata
│           └── handler.ts   ← Hook 邏輯
```

---

## 第一步：複製 Katrina 設定檔

將 `katrina/` 下面嘅 6 個 MD 文件複製去 OpenClaw workspace：

```bash
cp openclaw/katrina/IDENTITY.md ~/.openclaw/workspace/IDENTITY.md
cp openclaw/katrina/SOUL.md ~/.openclaw/workspace/SOUL.md
cp openclaw/katrina/AGENTS.md ~/.openclaw/workspace/AGENTS.md
cp openclaw/katrina/TOOLS.md ~/.openclaw/workspace/TOOLS.md
cp openclaw/katrina/HEARTBEAT.md ~/.openclaw/workspace/HEARTBEAT.md
cp openclaw/katrina/USER.md ~/.openclaw/workspace/USER.md
```

### 需要改嘅地方

- **TOOLS.md** 入面嘅路徑要改成新電腦嘅實際路徑
- **USER.md** 可以按需要填寫用戶資料

---

## 第二步：安裝 PDF 自動入庫 Hook

### 背景

OpenClaw 收到 WhatsApp 傳嚟嘅文件會存喺臨時目錄（`/tmp/openclaw/`），唔會自動搬去 RAG pipeline 嘅 inbox。呢個 hook 解決呢個問題。

### 原理

```
WhatsApp 發 PDF
    → OpenClaw 收到，存入臨時目錄
    → 觸發 message:preprocessed event
    → pdf-to-inbox hook 檢查 mediaType === "application/pdf"
    → 自動 copy 去 data/inbox/
    → watchdog 偵測到新文件，觸發入庫 pipeline
    → heartbeat 定期 check 狀態，通知用戶結果
```

### 安裝步驟

**1. 建立 hook 目錄：**

```bash
mkdir -p ~/.openclaw/hooks/pdf-to-inbox
```

**2. 複製 hook 文件：**

```bash
cp openclaw/katrina/hooks/pdf-to-inbox/HOOK.md ~/.openclaw/hooks/pdf-to-inbox/
cp openclaw/katrina/hooks/pdf-to-inbox/handler.ts ~/.openclaw/hooks/pdf-to-inbox/
```

**3. 修改 handler.ts 入面嘅 INBOX_DIR 路徑：**

打開 `~/.openclaw/hooks/pdf-to-inbox/handler.ts`，將第 4 行改成新電腦嘅實際路徑：

```typescript
const INBOX_DIR = "/你嘅實際路徑/GEO-Insurance-RAG/data/inbox";
```

**4. Enable hook：**

```bash
openclaw hooks enable pdf-to-inbox
```

**5. 重啟 gateway：**

```bash
openclaw gateway restart
```

**6. 驗證：**

```bash
openclaw hooks list
```

應該見到 `📄 pdf-to-inbox` 狀態係 `✓ ready`。

---

## 第三步：啟動 OpenSearch

RAG pipeline 嘅核心儲存，冇佢乜都做唔到。

```bash
docker compose -f docker/docker-compose.yml up -d
```

等幾秒，驗證 OpenSearch 有冇跑：

```bash
curl -s http://localhost:9200 | head -5
```

應該見到 `"cluster_name" : "docker-cluster"` 同 `"number" : "3.0.0"`。

### Container 一覽

| Container | Image | Port | 用途 |
|-----------|-------|------|------|
| geo-rag-opensearch | opensearch:3.0.0 | 9200 | Vector、graph、KV、doc status 儲存 |
| geo-rag-dashboards | opensearch-dashboards:3.0.0 | 5601 | Web UI（可選，debug 用） |

### 常用指令

```bash
docker compose -f docker/docker-compose.yml up -d     # 啟動
docker compose -f docker/docker-compose.yml down       # 停止
docker compose -f docker/docker-compose.yml down -v    # 停止 + 清除數據
docker ps                                               # 查看狀態
```

---

## 第四步：配置 MCP Server

喺 `~/.openclaw/openclaw.json` 加入 MCP server 設定：

```json
{
  "mcpServers": {
    "insurance-rag": {
      "command": "/你嘅實際路徑/GEO-Insurance-RAG/.venv/bin/python",
      "args": ["src/server.py"],
      "cwd": "/你嘅實際路徑/GEO-Insurance-RAG",
      "env": {
        "PYTHONPATH": "/你嘅實際路徑/GEO-Insurance-RAG"
      },
      "transport": "stdio"
    }
  }
}
```

---

## 驗證清單

全部做完之後，逐個驗證：

- [ ] `openclaw hooks list` 顯示 `pdf-to-inbox` 係 `✓ ready`
- [ ] 喺 WhatsApp send 一份 PDF 畀 Katrina
- [ ] 檢查 `data/inbox/` 有冇出現該 PDF
- [ ] 檢查入庫結果：Katrina 應該會喺下次 heartbeat 通知你
- [ ] 試問 Katrina 一個保險問題，確認 `query` tool 正常運作

---

## 故障排除

| 問題 | 檢查 |
|------|------|
| Hook 冇觸發 | `openclaw hooks list` 確認 enabled；重啟 gateway |
| PDF 冇出現喺 inbox | 檢查 handler.ts 入面嘅 INBOX_DIR 路徑係咪正確 |
| 入庫失敗 | 檢查 `data/failed/` 有冇文件；用 `get_doc_status` 查原因 |
| Katrina 冇反應 | 檢查 MCP server 設定；確認 OpenSearch 有冇跑緊 |
| Heartbeat 冇通知 | 確認 HEARTBEAT.md 已複製去 workspace 且唔係空白 |
