#!/usr/bin/env node

// MCP Server Template
//
// An MCP server that the IDE launches on startup. It dynamically loads
// project-specific tool schemas from .claude/mcp-schema.js, and bridges
// tool calls via HTTP POST to the project's local dev server.
//
// WHY A SEPARATE SERVER?
// IDEs (Cursor, Claude Desktop, VS Code) require MCP servers to be running
// BEFORE the IDE connects. A dev server that starts late (e.g. `yarn dev`)
// won't be discovered. This server starts instantly with the IDE and bridges
// requests to the dev server whenever it's available.
//
// SETUP:
// 1. Install dependencies: npm install @modelcontextprotocol/sdk dotenv zod
// 2. Configure your IDE's MCP settings to launch this script
// 3. Set environment variables: PROJECT_NAME and PORT
// 4. Create .claude/mcp-schema.js in your project (see templates/mcp-schema.js)
//
// The server resolves the schema path as: /workspace/$PROJECT_NAME/.claude/mcp-schema.js
// Adapt this path pattern to match your workspace layout.

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import dotenv from "dotenv";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));

process.chdir(scriptDir);

dotenv.config({
	path: path.join(scriptDir, ".env"),
	quiet: true,
});

const mcpServer = new McpServer({
	name: "my-mcp-server",
	version: "0.1.0",
});

// ============================================================================
// Local Tool Registration
// ============================================================================
// Register tools that run directly in this server process (no HTTP bridge).
// Use this for tools that don't need the dev server running.
//
// Example:
//
// import { myLocalTools } from "./tools/myLocalTools.js";
// myLocalTools.forEach((tool) => registerTool(tool));
//
// Where myLocalTools.js exports an array of tool definitions:
//
// export const myLocalTools = [
//   {
//     name: "example_tool",
//     title: "Example Tool",
//     description: "Description of what this tool does",
//     schema: z.object({
//       message: z.string().describe("A message to process"),
//     }),
//     async handler(cwd, args) {
//       // Tool implementation here
//       return { result: `Processed: ${args.message}` };
//     },
//   },
// ];

/**
 * Register a local tool with the MCP server.
 * The tool's handler runs in-process. Wraps with error handling.
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
				if (!roots.roots || roots.roots.length === 0) throw new Error("listRoots: no roots");
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
							text: JSON.stringify({ errors: [{ message: error.message }] }, null, 2),
						},
					],
					isError: true,
				};
			}
		},
	);
}

// ============================================================================
// Project-Specific Tool Loading (Dynamic Schema + HTTP Bridge)
// ============================================================================
// Loads .claude/mcp-schema.js from the project and bridges tool calls
// via HTTP POST to the project's local dev server.

async function loadProjectTools() {
	const projectName = process.env.PROJECT_NAME;
	const port = process.env.PORT;

	if (!projectName || !port) return;

	const schemaPath = `/workspace/${projectName}/.claude/mcp-schema.js`;

	if (!fs.existsSync(schemaPath)) {
		console.error(`[mcp-server] PROJECT_NAME and PORT are set, but schema not found: ${schemaPath}`);
		return;
	}

	let schema;
	try {
		schema = await import(schemaPath);
	} catch (error) {
		console.error(`[mcp-server] Failed to load MCP schema from ${schemaPath}: ${error.message}`);
		return;
	}

	const schemaFn = schema.default;
	if (typeof schemaFn !== "function") {
		console.error(`[mcp-server] MCP schema must default export a function. Got: ${typeof schemaFn}`);
		return;
	}

	const tools = schemaFn(z);
	if (!Array.isArray(tools)) {
		console.error(`[mcp-server] MCP schema function must return an array. Got: ${typeof tools}`);
		return;
	}

	const baseUrl = `http://localhost:${port}`;

	for (const tool of tools) {
		mcpServer.registerTool(
			tool.name,
			{
				title: tool.title,
				description: tool.description,
				inputSchema: tool.schema.shape,
			},
			async (args) => {
				try {
					const endpoint = `/api/debug/${tool.name}`;
					const url = `${baseUrl}${endpoint}`;

					const response = await fetch(url, {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify(args),
					});

					if (!response.ok) {
						const text = await response.text();
						throw new Error(`HTTP ${response.status}: ${text}`);
					}

					const result = await response.json();
					return {
						content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
					};
				} catch (error) {
					return {
						content: [
							{
								type: "text",
								text: JSON.stringify({ errors: [{ message: error.message }] }, null, 2),
							},
						],
						isError: true,
					};
				}
			},
		);
	}

	console.error(`[mcp-server] Loaded ${tools.length} project tool(s) from ${projectName}`);
}

// ============================================================================
// Entry Point
// ============================================================================

async function main() {
	await loadProjectTools();
	const transport = new StdioServerTransport();
	await mcpServer.connect(transport);
}

main().catch((error) => {
	console.error("MCP Server error:", error);
	process.exit(1);
});
