import fs from "node:fs";
import path from "node:path";

const DEBUG_LOG_PATH = path.join(process.cwd(), ".cursor", "debug.log");

export async function action({ request }) {
	if (request.method !== "POST") {
		return new Response("Method not allowed", { status: 405 });
	}

	const payload = await request.json().catch(() => null);
	if (payload == null || typeof payload !== "object") {
		return new Response("Bad request", { status: 400 });
	}

	const timestamp = Number(payload.timestamp) || Date.now();
	const id =
		typeof payload.id === "string" && payload.id
			? payload.id
			: `log_${timestamp}_${Math.random().toString(36).slice(2, 10)}`;
	const record = {
		...payload,
		id,
		timestamp,
		data: payload.data != null && typeof payload.data === "object" ? payload.data : {},
	};

	const dir = path.dirname(DEBUG_LOG_PATH);
	fs.mkdirSync(dir, { recursive: true });

	const line = JSON.stringify(record) + "\n";
	fs.appendFileSync(DEBUG_LOG_PATH, line);

	return new Response(null, { status: 204 });
}
