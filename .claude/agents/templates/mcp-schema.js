/**
 * MCP Schema Template
 *
 * Defines project-specific MCP tools that the MCP server exposes to IDE agents.
 * Each tool is bridged via HTTP POST to the local dev server.
 *
 * POSTS to: /api/debug/:toolName
 *
 * Place this file at: .claude/mcp-schema.js (project root)
 *
 * @param {import("zod").ZodType} z - Zod module, passed in by the MCP server.
 * @returns {Array} Array of tool definitions.
 */
export default function (z) {
	return [
		{
			name: "query_state",
			title: "Query Application State",
			description:
				"Retrieve current state of an application component. Use this to inspect runtime configuration, connection status, or cached data.",
			schema: z.object({
				component: z.string().describe("Component name to query (e.g., 'auth', 'cache', 'database')."),
			}),
		},
	];
}
