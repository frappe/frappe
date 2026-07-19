import { serverMessage } from "./client";
import { __ } from "@/lib/translate";

// Consumes the run SSE stream: POSTs the request, then parses `data:` blocks
// and hands each decoded event to `onEvent`.
async function postStream(method, body, onEvent, signal) {
	const resp = await fetch(`/api/method/${method}`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-Frappe-CSRF-Token": frappe.csrf_token,
		},
		body: JSON.stringify({ ...body, stream: true }),
		signal,
	});
	if (!resp.ok) {
		const data = await resp.json().catch(() => ({}));
		throw new Error(serverMessage(data) || __("Request failed ({0})", [resp.status]));
	}
	if (!resp.body) {
		throw new Error(__("Request failed ({0})", [resp.status]));
	}

	const reader = resp.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		const blocks = buffer.split("\n\n");
		buffer = blocks.pop();
		for (const block of blocks) {
			const line = block.split("\n").find((l) => l.startsWith("data: "));
			if (line) onEvent(JSON.parse(line.slice(6)));
		}
	}
}

export const startRun = (body, onEvent, signal) =>
	postStream("flow.api.start_run", body, onEvent, signal);
export const resumeRun = (body, onEvent, signal) =>
	postStream("flow.api.resume_run", body, onEvent, signal);
