import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const tunnelUrl = process.argv[2];

if (!tunnelUrl) {
  console.error("Please provide the Cloudflare Tunnel URL as an argument.");
  process.exit(1);
}

async function main() {
  console.error("Starting MCP proxy bridging stdio to:", tunnelUrl);

  const sseClient = new SSEClientTransport(new URL(tunnelUrl));
  await sseClient.start();
  console.error("Connected to remote SSE server.");

  const stdioServer = new StdioServerTransport();
  await stdioServer.start();
  console.error("Stdio transport started for Claude Desktop.");

  stdioServer.onmessage = (msg) => sseClient.send(msg).catch(console.error);
  sseClient.onmessage = (msg) => stdioServer.send(msg).catch(console.error);

  sseClient.onclose = () => process.exit(0);
  stdioServer.onclose = () => process.exit(0);
}

main().catch(err => {
  console.error("Fatal proxy error:", err);
  process.exit(1);
});
