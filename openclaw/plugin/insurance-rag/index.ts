import { McpBridge } from "./mcp-bridge.js";

interface PluginConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
  connectTimeoutMs?: number;
  callTimeoutMs?: number;
  tools?: ToolDef[];
}

interface ToolDef {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

// Default tool definitions matching the MCP server's 6 tools.
// These are declared statically so registerTool() can run synchronously
// inside register().  The actual MCP bridge connects lazily on first call.
const DEFAULT_TOOLS: ToolDef[] = [
  {
    name: "query",
    description:
      "Search insurance product information using semantic search and knowledge graph.",
    inputSchema: {
      type: "object",
      properties: {
        question: { type: "string", description: "The question to search for" },
        mode: {
          type: "string",
          description: "Search mode: auto, hybrid, local, global, naive",
          default: "auto",
        },
        top_k: { type: "number", description: "Number of results", default: 5 },
      },
      required: ["question"],
    },
  },
  {
    name: "ingest",
    description: "Process a single PDF document for ingestion.",
    inputSchema: {
      type: "object",
      properties: {
        file_path: { type: "string", description: "Path to the PDF file" },
      },
      required: ["file_path"],
    },
  },
  {
    name: "ingest_all",
    description: "Ingest all PDF files in the inbox directory.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "list_documents",
    description: "List all indexed documents with metadata.",
    inputSchema: {
      type: "object",
      properties: {
        status: { type: "string", description: "Filter by document status" },
        company: { type: "string", description: "Filter by company name" },
        product_type: { type: "string", description: "Filter by product type" },
        limit: { type: "number", default: 20 },
        offset: { type: "number", default: 0 },
      },
    },
  },
  {
    name: "delete_document",
    description: "Delete a document from the index.",
    inputSchema: {
      type: "object",
      properties: {
        document_id: { type: "string", description: "Document ID to delete" },
        confirm: {
          type: "boolean",
          description: "Must be true to confirm deletion",
          default: false,
        },
      },
      required: ["document_id"],
    },
  },
  {
    name: "get_system_status",
    description:
      "Get system health status including OpenSearch and API connectivity.",
    inputSchema: { type: "object", properties: {} },
  },
];

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

  // Use configured tool list or fall back to built-in defaults
  const toolDefs = config.tools ?? DEFAULT_TOOLS;

  // Track bridge readiness
  let bridgeReady = false;
  let bridgeConnecting: Promise<void> | null = null;

  const ensureBridge = async () => {
    if (bridgeReady) return;
    if (bridgeConnecting) {
      await bridgeConnecting;
      return;
    }
    bridgeConnecting = (async () => {
      logger.info("Lazy-connecting to MCP server...");
      await bridge.connect();
      bridgeReady = true;
      logger.info("MCP bridge connected (lazy)");
    })();
    await bridgeConnecting;
  };

  // Register tools SYNCHRONOUSLY in register() so they appear in every
  // plugin registry load — not just the gateway's cached copy.
  for (const toolDef of toolDefs) {
    const toolName = toolDef.name;

    api.registerTool({
      name: toolName,
      label: toolName,
      description: toolDef.description ?? "",
      parameters: toolDef.inputSchema ?? {
        type: "object",
        properties: {},
      },
      async execute(
        _toolCallId: string,
        params: Record<string, unknown>,
      ) {
        await ensureBridge();

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

  // Service handles eager connection at gateway startup and clean shutdown
  api.registerService({
    id: "insurance-rag-mcp",

    async start() {
      logger.info("Eagerly connecting to MCP server...");
      await ensureBridge();
      logger.info("MCP bridge ready");
    },

    async stop() {
      logger.info("Shutting down MCP bridge...");
      bridgeReady = false;
      bridgeConnecting = null;
      await bridge.close();
      logger.info("MCP bridge closed");
    },
  });
}
