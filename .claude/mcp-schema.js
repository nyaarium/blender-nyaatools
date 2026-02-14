/**
 * MCP Schema
 *
 * Defines project-specific MCP tools that nyaascripts exposes to IDE agents.
 * Each tool is bridged via HTTP POST to the local dev server.
 *
 * POSTS to: /api/debug/:toolName
 *
 * @param {import("zod").ZodType} z - Zod module, passed in by nyaascripts.
 * @returns {Array} Array of tool definitions.
 */
export default function (z) {
	return [
		{
			name: "foo",
			title: "Foo",
			description:
				"A simple test tool for validating the MCP bridge works. Accepts a numeric 'bar' parameter and echoes it back through the debug API.",
			schema: z.object({
				bar: z.number().describe("Some numeric value."),
			}),
		},
	];
}
