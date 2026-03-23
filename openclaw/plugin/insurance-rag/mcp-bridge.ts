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
