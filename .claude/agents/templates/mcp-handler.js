// MCP Server Template for AI Agent Control
// Exposes application state and operations to AI agents via Model Context Protocol
// Adapt tool definitions and handlers to your application's architecture

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

// ============================================================================
// Tool Schema Definitions (using Zod for validation)
// ============================================================================

// Example: Schema for querying application state
const QueryStateInputSchema = z.object({
  component: z.string().describe("Component name to query (e.g., 'auth', 'cache', 'database')"),
  includeMetrics: z.boolean().optional().describe("Include performance metrics in response"),
});

// Example: Schema for triggering application actions
const TriggerActionInputSchema = z.object({
  action: z.enum(["reload-config", "clear-cache", "run-healthcheck"]).describe("Action to trigger"),
  params: z.record(z.unknown()).optional().describe("Optional action parameters"),
});

// Example: Schema for reading debug logs
const ReadLogsInputSchema = z.object({
  hypothesisId: z.string().optional().describe("Filter by hypothesis ID for A/B debugging"),
  since: z.number().optional().describe("Unix timestamp - only return logs after this time"),
  limit: z.number().int().positive().optional().describe("Maximum entries to return"),
});

// ============================================================================
// Tool Definitions
// ============================================================================

const applicationTools = [
  {
    name: "query_application_state",
    title: "Query Application State",
    description:
      "Retrieve current state of application components. Use this to inspect runtime configuration, connection status, or cached data without manual intervention.",
    schema: QueryStateInputSchema,
    async handler(cwd, { component, includeMetrics }) {
      // TODO: Implement actual state querying for your application
      // Example implementation:
      // const state = await getComponentState(component);
      // if (includeMetrics) state.metrics = await getMetrics(component);
      // return state;

      return {
        component,
        status: "healthy",
        config: { /* component configuration */ },
        ...(includeMetrics && { metrics: { requestsPerSecond: 0, avgLatencyMs: 0 } }),
      };
    },
  },
  {
    name: "trigger_action",
    title: "Trigger Application Action",
    description:
      "Execute runtime operations like cache clearing, config reload, or health checks. Enables agents to control application behavior programmatically.",
    schema: TriggerActionInputSchema,
    async handler(cwd, { action, params }) {
      // TODO: Implement actual action handlers for your application
      // Example implementation:
      // switch (action) {
      //   case "reload-config": return await reloadConfiguration();
      //   case "clear-cache": return await clearApplicationCache();
      //   case "run-healthcheck": return await runHealthCheck();
      // }

      return {
        action,
        success: true,
        message: `Action '${action}' executed successfully`,
        params,
      };
    },
  },
  {
    name: "read_debug_logs",
    title: "Read Debug Logs",
    description:
      "Retrieve structured debug log entries written by the application. Supports filtering by hypothesis ID for A/B debugging scenarios.",
    schema: ReadLogsInputSchema,
    async handler(cwd, { hypothesisId, since, limit }) {
      // TODO: Implement actual log reading from your debug log location
      // Example implementation using debug-logger.js:
      // import { readDebugLog, getEntriesByHypothesis } from "./debug-logger.js";
      // let entries = hypothesisId ? getEntriesByHypothesis(hypothesisId) : readDebugLog();
      // if (since) entries = entries.filter(e => e.timestamp > since);
      // if (limit) entries = entries.slice(-limit);
      // return { entries, count: entries.length };

      return {
        entries: [],
        count: 0,
        filters: { hypothesisId, since, limit },
      };
    },
  },
];

// ============================================================================
// Server Setup
// ============================================================================

const scriptDir = path.dirname(fileURLToPath(import.meta.url));

dotenv.config({
  path: path.join(scriptDir, ".env"),
  quiet: true,
});

const mcpServer = new McpServer({
  name: "application-mcp",
  version: "0.1.0",
});

/**
 * Register a tool with the MCP server.
 * Wraps the handler with error handling and response formatting.
 */
function registerTool(tool) {
  mcpServer.registerTool(
    tool.name,
    {
      title: tool.title,
      description: tool.description,
      inputSchema: tool.schema.shape,
    },
    async (args) => {
      try {
        const roots = await mcpServer.server.listRoots();
        if (!roots.roots || roots.roots.length === 0) {
          throw new Error("No workspace roots available");
        }

        const cwd = fileURLToPath(roots.roots[0].uri);
        const result = await tool.handler(cwd, args);

        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (error) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ error: error.message }, null, 2),
            },
          ],
          isError: true,
        };
      }
    },
  );
}

// Register all application tools
applicationTools.forEach(registerTool);

// ============================================================================
// Entry Point
// ============================================================================

async function main() {
  const transport = new StdioServerTransport();
  await mcpServer.connect(transport);
}

main().catch((error) => {
  console.error("MCP Server error:", error);
  process.exit(1);
});
