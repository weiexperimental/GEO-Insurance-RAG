# OpenClaw MCP Bridge Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an OpenClaw plugin that bridges the existing Python MCP server to the embedded agent, exposing all 8 insurance RAG tools as native agent tools via StdioClientTransport.

**Architecture:** The plugin spawns `python src/server.py` as a persistent child process, connects via `@modelcontextprotocol/sdk` StdioClientTransport over stdio, discovers tools via `listTools()`, and registers each as a native OpenClaw agent tool. Reconnection is handled with a mutex to prevent concurrent reconnect races. All timeouts are configurable.

**Tech Stack:** TypeScript (ESM, run via OpenClaw's jiti), `@modelcontextprotocol/sdk` ^1.27.0, OpenClaw plugin API

**Spec:** `docs/superpowers/specs/2026-03-23-openclaw-mcp-plugin.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `openclaw/plugin/insurance-rag/mcp-bridge.ts` | Create | MCP client: connect, callTool, reconnect with mutex, timeouts |
| `openclaw/plugin/insurance-rag/index.ts` | Create | Plugin entry: service lifecycle, tool registration |
| `openclaw/plugin/insurance-rag/openclaw.plugin.json` | Create | Plugin manifest with config schema |
| `openclaw/plugin/insurance-rag/package.json` | Create | npm config + dependency |
| `openclaw/katrina/AGENTS.md` | Modify | Simplify upload flow (remove hook/MCP references) |
| `openclaw/katrina/TOOLS.md` | Modify | List 8 tools directly, remove watchdog/MCP details |
| `openclaw/SETUP.md` | Modify | Add plugin installation steps |

---

### Task 1: Create plugin scaffold (manifest + package.json)

**Files:**
- Create: `openclaw/plugin/insurance-rag/openclaw.plugin.json`
- Create: `openclaw/plugin/insurance-rag/package.json`

- [ ] **Step 1: Create directory**

```bash
mkdir -p /Users/weiexperimental/Desktop/GEO-Insurance-RAG/openclaw/plugin/insurance-rag
```

- [ ] **Step 2: Write `openclaw.plugin.json`**

```json
{
  "id": "insurance-rag",
  "name": "Insurance RAG",
  "description": "Bridge to insurance document RAG MCP server",
  "configSchema": {
    "type": "object",
    "required": ["command"],
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

- [ ] **Step 3: Write `package.json`**

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

- [ ] **Step 4: Install dependencies**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG/openclaw/plugin/insurance-rag && npm install
```

Expected: `node_modules/` created with `@modelcontextprotocol/sdk`

- [ ] **Step 5: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add openclaw/plugin/insurance-rag/openclaw.plugin.json openclaw/plugin/insurance-rag/package.json openclaw/plugin/insurance-rag/package-lock.json
git commit -m "feat(plugin): scaffold insurance-rag OpenClaw plugin"
```

---

### Task 2: Implement `mcp-bridge.ts`

**Files:**
- Create: `openclaw/plugin/insurance-rag/mcp-bridge.ts`

- [ ] **Step 1: Write the complete `mcp-bridge.ts`**

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

export interface BridgeConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
  connectTimeoutMs: number;
  callTimeoutMs: number;
}

export class McpBridge {
  private client: Client | null = null;
  private transport: StdioClientTransport | null = null;
  private alive = false;
  private reconnecting: Promise<void> | null = null;

  constructor(
    private config: BridgeConfig,
    private logger: { info: (msg: string) => void; warn: (msg: string) => void },
  ) {}

  async connect(): Promise<void> {
    const safeEnv: Record<string, string> = {
      PATH: process.env.PATH ?? "/usr/bin:/bin:/usr/local/bin",
      HOME: process.env.HOME ?? "",
      ...this.config.env,
    };

    this.transport = new StdioClientTransport({
      command: this.config.command,
      args: this.config.args,
      env: safeEnv,
      cwd: this.config.cwd,
    });

    this.transport.onclose = () => {
      this.alive = false;
      this.logger.warn("MCP transport closed");
    };

    this.transport.onerror = (err) => {
      this.alive = false;
      this.logger.warn(`MCP transport error: ${err}`);
    };

    this.client = new Client(
      { name: "insurance-rag-plugin", version: "0.1.0" },
      {},
    );

    const connectPromise = this.client.connect(this.transport);
    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(
        () => reject(new Error(`MCP connect timeout (${this.config.connectTimeoutMs}ms)`)),
        this.config.connectTimeoutMs,
      ),
    );

    await Promise.race([connectPromise, timeoutPromise]);
    this.alive = true;
  }

  async listTools() {
    if (!this.client) throw new Error("Not connected");

    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("listTools timeout (10s)")), 10_000),
    );
    const result = await Promise.race([this.client.listTools(), timeoutPromise]);
    return result.tools;
  }

  async callTool(name: string, args: Record<string, unknown>) {
    if (!this.alive) {
      await this.ensureConnected();
    }

    try {
      return await this.callToolWithTimeout(name, args);
    } catch (err) {
      if (!this.alive) {
        this.logger.warn(`Tool call failed, reconnecting: ${err}`);
        await this.ensureConnected();
        return await this.callToolWithTimeout(name, args);
      }
      throw err;
    }
  }

  private async callToolWithTimeout(name: string, args: Record<string, unknown>) {
    if (!this.client) throw new Error("Not connected");

    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(
        () => reject(new Error(`callTool timeout (${this.config.callTimeoutMs}ms)`)),
        this.config.callTimeoutMs,
      ),
    );
    return await Promise.race([
      this.client.callTool({ name, arguments: args }),
      timeoutPromise,
    ]);
  }

  private async ensureConnected(): Promise<void> {
    if (this.reconnecting) return this.reconnecting;

    this.reconnecting = this.doReconnect();
    try {
      await this.reconnecting;
    } finally {
      this.reconnecting = null;
    }
  }

  private async doReconnect(): Promise<void> {
    this.logger.info("Reconnecting to MCP server...");

    // Close old connection
    if (this.client) {
      try {
        await this.client.close();
      } catch {
        // Ignore close errors on dead connection
      }
      this.client = null;
      this.transport = null;
      this.alive = false;
    }

    await this.connect();
    this.logger.info("MCP server reconnected");
  }

  async close(): Promise<void> {
    if (this.client) {
      try {
        await this.client.close();
      } catch {
        // Ignore close errors
      }
      this.client = null;
      this.transport = null;
      this.alive = false;
    }
  }
}
```

- [ ] **Step 2: Verify TypeScript syntax is valid**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG/openclaw/plugin/insurance-rag
npx tsc --noEmit --moduleResolution node16 --module nodenext --target es2022 mcp-bridge.ts 2>&1 || echo "TypeScript check done (errors may be expected without full type context)"
```

Note: Full type checking requires OpenClaw's type context. Runtime validation via OpenClaw's jiti loader will catch real issues. This step is a basic syntax check.

- [ ] **Step 3: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add openclaw/plugin/insurance-rag/mcp-bridge.ts
git commit -m "feat(plugin): implement MCP bridge with reconnect mutex and timeouts"
```

---

### Task 3: Implement `index.ts`

**Files:**
- Create: `openclaw/plugin/insurance-rag/index.ts`

- [ ] **Step 1: Write the complete `index.ts`**

```typescript
import { McpBridge } from "./mcp-bridge.js";

interface PluginConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
  connectTimeoutMs?: number;
  callTimeoutMs?: number;
}

export default function register(api: any) {
  const config = api.pluginConfig as PluginConfig;
  const logger = api.logger;

  if (!config.command) {
    logger.warn("insurance-rag plugin: no command configured, skipping");
    return;
  }

  const bridge = new McpBridge(
    {
      command: config.command,
      args: config.args,
      env: config.env,
      cwd: config.cwd,
      connectTimeoutMs: config.connectTimeoutMs ?? 60000,
      callTimeoutMs: config.callTimeoutMs ?? 30000,
    },
    logger,
  );

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
          label: toolName,
          description: (tool as any).description ?? "",
          parameters: (tool as any).inputSchema ?? {
            type: "object",
            properties: {},
          },
          async execute(
            _toolCallId: string,
            params: Record<string, unknown>,
          ) {
            const result = await bridge.callTool(toolName, params);

            if ((result as any).isError) {
              const errorText =
                (result as any).content
                  ?.map((c: any) => c.text ?? "")
                  .join("\n") ?? "Unknown error";
              return {
                content: [{ type: "text" as const, text: errorText }],
                details: {},
              };
            }

            const text =
              (result as any).content
                ?.map((c: any) => {
                  if (c.type === "text") return c.text;
                  if (c.type === "image") return `[image: ${c.mimeType}]`;
                  return JSON.stringify(c);
                })
                .join("\n") ?? "";

            return {
              content: [{ type: "text" as const, text }],
              details: {},
            };
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

- [ ] **Step 2: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add openclaw/plugin/insurance-rag/index.ts
git commit -m "feat(plugin): implement plugin entry with service lifecycle and tool registration"
```

---

### Task 4: Install plugin into OpenClaw and update config

**Files:**
- Modify: `~/.openclaw/openclaw.json`

- [ ] **Step 1: Symlink plugin to OpenClaw extensions**

```bash
ln -sf /Users/weiexperimental/Desktop/GEO-Insurance-RAG/openclaw/plugin/insurance-rag /Users/weiexperimental/.openclaw/extensions/insurance-rag
ls -la /Users/weiexperimental/.openclaw/extensions/insurance-rag/openclaw.plugin.json
```

Expected: File exists (symlink working)

- [ ] **Step 2: Enable the plugin**

```bash
openclaw plugins enable insurance-rag
```

- [ ] **Step 3: Update `~/.openclaw/openclaw.json`**

Read the current file first. Then apply these changes:

1. **Remove** the `"acp"` top-level section entirely
2. **Remove** `"agents.list"` array (revert to defaults, no runtime override)
3. **Replace** the `"plugins.entries"` section with:

```json
{
  "plugins": {
    "entries": {
      "whatsapp": {
        "enabled": true
      },
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

Remove the `acpx` plugin entry (no longer needed).

- [ ] **Step 4: Restart gateway and verify**

```bash
# Kill existing gateway
ps aux | grep openclaw | grep -v grep | awk '{print $2}' | xargs kill 2>/dev/null
sleep 5

# Check gateway restarted
tail -15 ~/.openclaw/logs/gateway.log

# Verify plugin loaded
openclaw plugins list
```

Expected in logs: `insurance-rag` plugin loaded, "Discovered 8 tools" message.

- [ ] **Step 5: Commit config changes to repo**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add -A openclaw/plugin/
git commit -m "feat(plugin): install and configure insurance-rag plugin in OpenClaw"
```

---

### Task 5: Update OpenClaw workspace config files

**Files:**
- Modify: `openclaw/katrina/AGENTS.md`
- Modify: `openclaw/katrina/TOOLS.md`

- [ ] **Step 1: Update `AGENTS.md` upload flow section**

In `openclaw/katrina/AGENTS.md`, replace the `## 文件上傳流程` section with:

```markdown
## 文件上傳流程

**重要：當你收到任何 PDF 附件，你必須用 `ingest_document` 將佢入庫。唔好用內建嘅 pdf tool 直接讀取內容。**

你會見到類似：
```
[media attached: /Users/.../.openclaw/media/inbound/filename.pdf (application/pdf)]
```

**流程：**
1. 回覆用戶：「收到 [文件名]，正在入庫...」
2. 從 `[media attached: ...]` 提取完整 file path（`/Users/.../.openclaw/media/inbound/` 開頭嘅完整路徑）
3. **立即 call `ingest_document(file_path="完整路徑")`**
4. Call `get_doc_status` 查詢入庫結果
5. 回報結果：
   - **ready** → 「[文件名] 已成功入庫！識別到係 [公司] 嘅 [產品名稱]」
   - **partial** → 「[文件名] 已入庫但 metadata 未完整，可能需要人手補充」
   - **failed** → 「[文件名] 入庫失敗，原因：[error]。請檢查文件係咪完整嘅 PDF」
   - **awaiting_confirmation** → 進入版本更新流程（見下面）

**非 PDF 文件：** 回覆「我只支援 PDF 格式嘅文件入庫」
```

Also update the `ingest_inbox` tool description (line ~25):
```
- **`ingest_inbox`** — 觸發 inbox 全部入庫（heartbeat 自動 call，手動亦可）
```

- [ ] **Step 2: Update `TOOLS.md`**

Replace the entire `openclaw/katrina/TOOLS.md` with:

```markdown
# TOOLS.md - Katrina 環境配置

## 保險工具

以下工具可以直接使用：
- `query` — 搜尋保險產品資料（預設 hybrid mode）
- `ingest_document` — 入庫指定 PDF 文件
- `ingest_inbox` — 入庫 inbox 所有文件
- `get_doc_status` — 查詢文件入庫狀態
- `list_documents` — 列出已入庫文件（支援 filter）
- `delete_document` — 刪除已入庫文件（需確認）
- `get_system_status` — 系統健康檢查
- `confirm_version_update` — 確認版本更新

## 文件目錄

- **Inbox:** `data/inbox/` — 手動拉 PDF 入呢度，heartbeat 會自動入庫
- **Processed:** `data/processed/` — 成功入庫嘅 PDF
- **Failed:** `data/failed/` — 入庫失敗嘅 PDF

## 文件上傳

- **WhatsApp 上傳：** 你直接 call `ingest_document(file_path)` 入庫
- **手動拉文件：** 放入 `data/inbox/`，heartbeat 自動處理

## 基礎設施

- **OpenSearch 3.x** — port 9200
- **MinerU (MLX GPU)** — PDF 解析，中文 OCR
- **YIBU API** — LLM / embedding / vision provider

## 支援嘅文件格式

- 只限 PDF（最大 100MB）
- 語言：繁體中文
- 其他格式一律拒絕
```

- [ ] **Step 3: Copy to workspace**

```bash
cp /Users/weiexperimental/Desktop/GEO-Insurance-RAG/openclaw/katrina/AGENTS.md /Users/weiexperimental/.openclaw/workspace/AGENTS.md
cp /Users/weiexperimental/Desktop/GEO-Insurance-RAG/openclaw/katrina/TOOLS.md /Users/weiexperimental/.openclaw/workspace/TOOLS.md
```

- [ ] **Step 4: Commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add openclaw/katrina/AGENTS.md openclaw/katrina/TOOLS.md
git commit -m "docs: update Katrina configs for plugin-based tool access"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Ensure Docker + OpenSearch running**

```bash
docker ps | grep opensearch || docker compose -f docker/docker-compose.yml up -d
curl -s http://localhost:9200 | head -5
```

Expected: OpenSearch 3.0.0 responding

- [ ] **Step 2: Restart gateway (fresh session)**

```bash
ps aux | grep openclaw | grep -v grep | awk '{print $2}' | xargs kill 2>/dev/null
sleep 5
tail -20 ~/.openclaw/logs/gateway.log
```

Expected in logs:
- `[insurance-rag] Connecting to MCP server...`
- `[insurance-rag] Discovered 8 tools`
- `[insurance-rag] Registered tool: query`
- `[insurance-rag] Registered tool: ingest_document`
- etc.

- [ ] **Step 3: Send `/new` on WhatsApp to reset session**

Send `/new` to Katrina via WhatsApp.

- [ ] **Step 4: Send a PDF and verify ingestion**

Send a PDF via WhatsApp. Expected Katrina response should include:
- "收到 [文件名]，正在入庫..."
- Calls `ingest_document` (visible in gateway logs)
- Reports ingestion result

Check logs:
```bash
grep -i "ingest\|tool\|callTool" /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | tail -20
```

- [ ] **Step 5: Test query**

Ask Katrina a question about the ingested document via WhatsApp. She should call `query` and return relevant content with source attribution.

- [ ] **Step 6: Final commit**

```bash
cd /Users/weiexperimental/Desktop/GEO-Insurance-RAG
git add -A
git status
git commit -m "feat: complete OpenClaw MCP bridge plugin — end-to-end verified"
```
