/**
 * MCP Schema
 *
 * Defines project-specific MCP tools that switchboard connector exposes to IDE agents.
 * Each tool is invoked on game clients connected via WebSocket.
 *
 * @param {import("zod").ZodType} z - Zod module, passed in by switchboard connector.
 * @returns {Array} Array of tool definitions.
 */
export default function (z) {
	return [
		{
			name: "foo",
			title: "Foo",
			description:
				"A simple test tool for validating the connector works. Accepts a numeric 'bar' parameter and echoes it back through the debug API.",
			schema: z.object({
				bar: z.number().describe("Some numeric value."),
			}),
		},
	];
}