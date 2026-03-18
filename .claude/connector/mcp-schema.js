/**
 * MCP Schema
 *
 * Defines project-specific MCP tools that project-mcp-connector exposes to IDE agents.
 * Each tool is invoked on game clients connected via WebSocket.
 *
 * @param {import("zod").ZodType} z - Zod module, passed in by project-mcp-connector.
 * @returns {Array} Array of tool definitions.
 */
export default function (z) {
	return [
		{
			name: "foo",
			title: "Foo",
			description:
				"A simple test tool for validating the project-mcp-connector works. Accepts a numeric 'bar' parameter and echoes it back through the debug API.",
			schema: z.object({
				bar: z.number().describe("Some numeric value."),
			}),
		},
	];
}