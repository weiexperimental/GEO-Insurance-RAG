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
