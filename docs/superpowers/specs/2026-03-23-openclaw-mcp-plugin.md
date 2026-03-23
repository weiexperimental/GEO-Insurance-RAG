# OpenClaw MCP Bridge Plugin — Design Spec

**日期：** 2026-03-23
**狀態：** Draft

---

## 背景

OpenClaw 嘅 embedded agent（Katrina）冇 native MCP support。MCP tools 只有喺 ACP harness session 先有，但 WhatsApp 對話用 embedded agent。

呢個 plugin 將我哋現有嘅 MCP server（`src/server.py`，FastMCP 3.x，8 個 tools）橋接到 embedded agent，令 Katrina 直接見到同使用所有 8 個保險工具。

### 驗證

呢個架構已被業界驗證：
- OpenClaw 內部嘅 Chrome MCP 用同一個 pattern（persistent `StdioClientTransport` + `Client`）
- `openclaw-mcp-adapter` (github.com/androidStern-personal) 用同一個架構
- OpenClaw 官方正開發 native MCP support（PR #44916），config schema 一致

---

## 架構

```
┌─────────────────────────────────────────────────┐
│ OpenClaw Gateway (Node.js)                       │
│                                                   │
│  Plugin: insurance-rag                            │
│  ┌─────────────────────────────────────────────┐ │
│  │ Service (start/stop lifecycle)               │ │
│  │                                             │ │
│  │ start():                                    │ │
│  │   spawn python src/server.py (persistent)   │ │
│  │   → StdioClientTransport connect (60s TO)   │ │
│  │   → client.listTools() → 8 tools            │ │
│  │   → registerTool × 8                        │ │
│  │                                             │ │
│  │ execute(tool_call):                         │ │
│  │   check pid !== null (alive?)               │ │
│  │   → dead? reconnect (with mutex)            │ │
│  │   → client.callTool(name, params) (30s TO)  │ │
│  │   → return result                           │ │
│  │                                             │ │
│  │ stop():                                     │ │
│  │   client.close()                            │ │
│  │   → SIGTERM → SIGKILL escalation            │ │
│  └──────────────────┬──────────────────────────┘ │
│                     │ stdio (JSON-RPC 2.0)        │
│  Katrina (embedded) │                             │
│  sees 8 tools ──────┘                             │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│ Python MCP Server (persistent child process)     │
│ src/server.py — FastMCP 3.x — 零改動             │
│ Tools: query, ingest_document, ingest_inbox,     │
│ get_doc_status, list_documents, delete_document, │
│ get_system_status, confirm_version_update         │
└─────────────────────────────────────────────────┘
```

---

## 文件結構

```
openclaw/plugin/insurance-rag/
├── openclaw.plugin.json     # Plugin manifest
├── package.json             # Dependencies (@modelcontextprotocol/sdk)
├── index.ts                 # Entry: service lifecycle + tool registration
└── mcp-bridge.ts            # MCP client: connect, callTool, reconnect
```

放喺 project repo 入面。安裝到 OpenClaw 時用 symlink：
```bash
ln -s /path/to/GEO-Insurance-RAG/openclaw/plugin/insurance-rag ~/.openclaw/extensions/insurance-rag
openclaw plugins enable insurance-rag
```

---

## 組件設計

### `mcp-bridge.ts` — MCP Client Bridge (~120 行)

負責同 Python MCP server 嘅所有通訊。

```typescript
class McpBridge {
  private client: Client | null = null;
  private transport: StdioClientTransport | null = null;
  private reconnecting: Promise<void> | null = null;  // mutex

  constructor(private config: BridgeConfig, private logger: Logger) {}

  private alive: boolean = false;

  async connect(): Promise<void>
  // 1. spawn python process via StdioClientTransport with cwd
  // 2. set transport.onclose = () => { this.alive = false }
  // 3. client.connect(transport) with Promise.race timeout
  // 4. this.alive = true
  // 5. throw if timeout exceeded
  // Env: only PATH + HOME + config.env (唔傳 process.env)
  // cwd: config.cwd (確保 Python server 嘅 relative paths 正確)

  async listTools(): Promise<Tool[]>
  // client.listTools() with timeout

  async callTool(name: string, args: Record<string, unknown>): Promise<CallToolResult>
  // 1. check isAlive()
  // 2. if dead → await ensureConnected()
  // 3. client.callTool with AbortSignal.timeout
  // 4. on connection error → ensureConnected() → retry once
  // 5. return result

  private isAlive(): boolean
  // return this.alive (set by transport.onclose handler)

  private async ensureConnected(): Promise<void>
  // Reconnect mutex:
  // if (this.reconnecting) return this.reconnecting;
  // this.reconnecting = this._reconnect();
  // try { await this.reconnecting } finally { this.reconnecting = null }

  private async _reconnect(): Promise<void>
  // 1. close old transport (ignore errors)
  // 2. connect() with fresh client + transport

  async close(): Promise<void>
  // 1. client.close() (SDK handles SIGTERM → SIGKILL)
  // 2. null out references
}
```

**Key design decisions：**
- **Reconnect mutex** — 只有一個 reconnect 喺 fly，其他 callers await 同一個 Promise
- **Env isolation** — 只傳 `PATH` + `HOME` + config 指定嘅 env vars，唔 spread `process.env`
- **Timeout everywhere** — connect (60s)、listTools (10s)、callTool (30s)
- **Alive check** — listen `transport.onclose` → set `alive = false`（唔靠 internal `pid` property）
- **cwd** — spawn Python process 時傳 `cwd` 確保 relative paths 正確

### `index.ts` — Plugin Entry (~80 行)

```typescript
export default function register(api: any) {
  const config = api.pluginConfig as PluginConfig;
  const logger = api.logger;
  const bridge = new McpBridge({
    command: config.command,
    args: config.args,
    env: config.env,
    cwd: config.cwd,
    connectTimeoutMs: config.connectTimeoutMs ?? 60000,
    callTimeoutMs: config.callTimeoutMs ?? 30000,
  }, logger);

  api.registerService({
    id: "insurance-rag-mcp",

    async start() {
      logger.info("Connecting to MCP server...");
      await bridge.connect();

      const tools = await bridge.listTools();
      logger.info(`Discovered ${tools.length} tools`);

      for (const tool of tools) {
        const toolName = tool.name;
        api.registerTool({
          name: toolName,
          label: toolName,  // required by AnyAgentTool
          description: tool.description ?? "",
          parameters: tool.inputSchema ?? { type: "object", properties: {} },
          async execute(_toolCallId: string, params: Record<string, unknown>) {
            const result = await bridge.callTool(toolName, params);

            if (result.isError) {
              const errorText = result.content
                ?.map((c: any) => c.text ?? "")
                .join("\n") ?? "Unknown error";
              return { content: [{ type: "text", text: errorText }], details: {} };
            }

            const text = result.content
              ?.map((c: any) => {
                if (c.type === "text") return c.text;
                if (c.type === "image") return `[image: ${c.mimeType}]`;
                return JSON.stringify(c);
              })
              .join("\n") ?? "";
            return { content: [{ type: "text", text }], details: {} };
          },
        });
        logger.info(`Registered tool: ${toolName}`);
      }
    },

    async stop() {
      logger.info("Shutting down MCP bridge...");
      await bridge.close();
      logger.info("MCP bridge closed");
    },
  });
}
```

> **Note on `api: any`：** OpenClaw 唔 export plugin API types 畀外部用。同現有 plugins（tlon、lobster）一樣用 `any`。
> Runtime 會驗證 `registerTool` 嘅 shape 係咪正確。

**Key design decisions：**
- **Tool names 直接用 MCP server 嘅** — 唔加 prefix（只有一個 server）
- **Content mapping** — text 直接傳，image 標記 type，其他 JSON stringify
- **Error 同 success 分開處理** — `isError` flag
- **用 `api.logger`** — structured logging，唔用 `console.log`

### `openclaw.plugin.json` — Manifest

```json
{
  "id": "insurance-rag",
  "name": "Insurance RAG",
  "description": "Bridge to insurance document RAG MCP server",
  "configSchema": {
    "type": "object",
    "required": ["command"],
    "additionalProperties": false,
    "properties": {
      "command": {
        "type": "string",
        "description": "Python executable path"
      },
      "args": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Arguments (e.g. path to server.py)"
      },
      "env": {
        "type": "object",
        "additionalProperties": { "type": "string" },
        "description": "Environment variables for the MCP server"
      },
      "cwd": {
        "type": "string",
        "description": "Working directory for the MCP server process"
      },
      "connectTimeoutMs": {
        "type": "number",
        "default": 60000,
        "description": "Connection timeout in milliseconds"
      },
      "callTimeoutMs": {
        "type": "number",
        "default": 30000,
        "description": "Per-tool-call timeout in milliseconds"
      }
    }
  }
}
```

### `package.json`

```json
{
  "name": "insurance-rag-plugin",
  "version": "0.1.0",
  "type": "module",
  "openclaw": {
    "extensions": ["./index.ts"]
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.27.0"
  }
}
```

唔需要額外 dependencies — `@modelcontextprotocol/sdk` 已經喺 OpenClaw 入面 ship 咗，但明確聲明確保版本兼容。

---

## OpenClaw Config 改動

### `~/.openclaw/openclaw.json`

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "openai-codex/gpt-5.4" },
      "workspace": "/Users/weiexperimental/.openclaw/workspace"
    }
  },
  "plugins": {
    "entries": {
      "insurance-rag": {
        "enabled": true,
        "config": {
          "command": "/Users/weiexperimental/Desktop/GEO-Insurance-RAG/.venv/bin/python",
          "args": ["/Users/weiexperimental/Desktop/GEO-Insurance-RAG/src/server.py"],
          "env": {
            "PYTHONPATH": "/Users/weiexperimental/Desktop/GEO-Insurance-RAG"
          },
          "cwd": "/Users/weiexperimental/Desktop/GEO-Insurance-RAG",
          "connectTimeoutMs": 60000,
          "callTimeoutMs": 30000
        }
      }
    }
  }
}
```

**移除嘅 config：**
- `acp` section（唔需要）
- `agents.list[0].runtime` block（返回 embedded）
- `plugins.entries.acpx.config.mcpServers`（plugin 取代）

---

## OpenClaw Workspace 改動

### AGENTS.md — 簡化文件上傳流程

移除所有 hook/MCP 技術細節。Katrina 直接用 tools：

```markdown
## 文件上傳流程

**重要：當你收到任何 PDF 附件，你必須用 `ingest_document` 將佢入庫。**

你會見到類似：
[media attached: /Users/.../.openclaw/media/inbound/filename.pdf (application/pdf)]

**流程：**
1. 回覆用戶：「收到 [文件名]，正在入庫...」
2. 從 [media attached: ...] 提取完整 file path
3. Call `ingest_document(file_path="完整路徑")`
4. Call `get_doc_status` 查詢結果
5. 回報結果
```

### TOOLS.md — 移除 MCP 技術細節

```markdown
## 保險工具

以下工具可以直接使用：
- `query` — 搜尋保險產品資料
- `ingest_document` — 入庫 PDF 文件
- `ingest_inbox` — 入庫 inbox 所有文件
- `get_doc_status` — 查詢入庫狀態
- `list_documents` — 列出已入庫文件
- `delete_document` — 刪除文件
- `get_system_status` — 系統健康檢查
- `confirm_version_update` — 確認版本更新
```

---

## Edge Cases

### Python server 啟動慢（30+ 秒）
- `connect()` 有 60 秒 timeout
- OpenSearch retry loop 喺 server 入面（最多 60 秒）
- RAG engine init 需要建 index（首次啟動較慢）
- 總共最多 ~120 秒首次啟動，之後 <5 秒

### Python process crash
- `isAlive()` check `transport.pid`
- 下次 tool call 自動 reconnect
- Reconnect mutex 防並發衝突

### Gateway restart
- `stop()` call `client.close()` → SDK 處理 SIGTERM/SIGKILL
- 新啟動 `start()` spawn fresh process
- 冇 orphan process 風險（SDK 嘅 `close()` 有 kill escalation）

### 並發 tool calls
- MCP protocol (JSON-RPC 2.0) 支援 concurrent requests
- Python asyncio 處理並發
- Ingestion pipeline 有 `_lock` 保證順序入庫

---

## 唔做嘅嘢（YAGNI）

- ~~HTTP transport~~ — 只用 stdio
- ~~Multi-server support~~ — 只有一個 server
- ~~Tool prefix~~ — 唔需要
- ~~Dynamic tool re-discovery~~ — Tools 唔會變
- ~~Env var interpolation~~ — 直接寫值
- ~~PID file~~ — SDK 嘅 close() 已處理 process cleanup
- ~~Graceful drain~~ — MCP call 有 timeout，唔會永久 hang

---

## 安裝步驟

```bash
# 1. 安裝 dependencies
cd openclaw/plugin/insurance-rag
npm install

# 2. Symlink 到 OpenClaw extensions
ln -s $(pwd)/openclaw/plugin/insurance-rag ~/.openclaw/extensions/insurance-rag

# 3. Enable plugin
openclaw plugins enable insurance-rag

# 4. 更新 openclaw.json（加 plugin config）

# 5. Restart gateway
openclaw gateway restart

# 6. 驗證
openclaw plugins list  # 應該見到 insurance-rag ✓
```

---

## 測試計劃

| 場景 | 方法 |
|------|------|
| Plugin 啟動 + tool discovery | Gateway start，check logs 有 "Discovered 8 tools" |
| Tool call 成功 | WhatsApp send PDF，Katrina call `ingest_document` |
| Python crash + reconnect | Kill python process，下次 tool call 應自動 reconnect |
| Connect timeout | 停 OpenSearch → server 啟動慢 → 確認 60s 後 timeout |
| Call timeout | Mock 一個永不返回嘅 tool → 確認 30s 後 timeout |
| Gateway shutdown | `openclaw gateway restart`，確認 Python process 冇 orphan |
| 並發 calls | 連續 send 2 份 PDF，確認兩個都入庫成功 |

---

## 改動摘要

| 文件 | 動作 |
|------|------|
| `openclaw/plugin/insurance-rag/openclaw.plugin.json` | 新建 |
| `openclaw/plugin/insurance-rag/package.json` | 新建 |
| `openclaw/plugin/insurance-rag/index.ts` | 新建 (~80 行) |
| `openclaw/plugin/insurance-rag/mcp-bridge.ts` | 新建 (~120 行) |
| `~/.openclaw/openclaw.json` | 修改（移除 acp，加 plugin config） |
| `~/.openclaw/workspace/AGENTS.md` | 修改（簡化上傳流程） |
| `~/.openclaw/workspace/TOOLS.md` | 修改（列出 8 個 tools） |
| `openclaw/katrina/AGENTS.md` | 修改（同步） |
| `openclaw/katrina/TOOLS.md` | 修改（同步） |
| `openclaw/SETUP.md` | 修改（加 plugin 安裝步驟） |
| `src/server.py` | **零改動** |
| `src/ingestion.py` | **零改動** |
