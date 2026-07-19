import { __ } from "@/lib/translate";

// Read-only data fetches over the desk's whitelisted client API.
function getList(doctype, options) {
	return frappe.xcall("frappe.client.get_list", { doctype, ...options });
}

export const loadAgents = () =>
	getList("Flow Agent", { filters: { enabled: 1 }, fields: ["name", "title"], limit: 50 });

export const loadModels = () =>
	getList("Flow Model", { filters: { enabled: 1 }, fields: ["name", "title"], limit: 50 });

export const loadHistory = () =>
	getList("Flow Session", {
		filters: { owner: frappe.session.user, source: ["!=", "Trigger"] },
		fields: ["name", "title", "modified"],
		order_by: "modified desc",
		limit: 15,
	});

// Escape LIKE wildcards so a literal % or _ matches itself, not "anything".
const escapeLike = (s) => s.replace(/[\\%_]/g, "\\$&");

export const searchSessions = (query) =>
	getList("Flow Session", {
		filters: {
			owner: frappe.session.user,
			source: ["!=", "Trigger"],
			title: ["like", `%${escapeLike(query)}%`],
		},
		fields: ["name", "title", "modified"],
		order_by: "modified desc",
		limit: 20,
	});

export const getSession = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "Flow Session", name });

export const getPausedRun = (session) =>
	getList("Flow Run", {
		filters: { session, status: "Paused" },
		fields: ["name", "questions"],
		order_by: "creation desc",
		limit: 1,
	});

// Feedback the user already gave on this session's runs, to restore thumbs state on reload.
export const getRunFeedback = (session) =>
	getList("Flow Run", {
		filters: { session, feedback_rating: ["is", "set"] },
		fields: ["name", "feedback_rating", "feedback_comment"],
		limit: 100,
	});

// Record thumbs feedback on a run; optionally store a Down comment as agent memory.
export const submitFeedback = (args) => frappe.xcall("flow.api.submit_feedback", args);

// Fail any Running run left behind by a stream that was cut off (refresh/navigation),
// so a reloaded session isn't blocked from starting the next turn.
export const recoverSession = (session) => frappe.xcall("flow.api.recover_session", { session });

// Stop a run at the user's request: finalize an aborted stream's run or terminate a
// paused run so the agent won't continue.
export const stopRun = (run_name) => frappe.xcall("flow.api.stop_run", { run_name });

// Map of the agent's tool slugs → requires_confirmation, so the panel can tell an
// approval tool call from an inline one.
export const getAgentTools = (agent) => frappe.xcall("flow.api.get_agent_tools", { agent });

// Upload a file as private, returning the created File doc. The chat attachment
// flow needs the File name to stage it via attachFile.
export async function uploadFile(file) {
	const form = new FormData();
	form.append("file", file, file.name);
	form.append("is_private", "1");

	const resp = await fetch("/api/method/upload_file", {
		method: "POST",
		headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
		body: form,
	});
	const data = await resp.json().catch(() => ({}));
	if (!resp.ok) throw new Error(serverMessage(data) || __("Upload failed ({0})", [resp.status]));
	return data.message;
}

// Validate and stage an uploaded File for use as a chat attachment. Returns chip
// metadata; throws (unsupported type, unreadable, …) which surfaces on the chip.
export const attachFile = (file) => frappe.xcall("flow.api.attach_file", { file });

// Extract the human-readable message from a frappe error body.
export function serverMessage(data) {
	try {
		const msgs = JSON.parse(data._server_messages || "[]");
		if (msgs.length) return JSON.parse(msgs[0]).message;
	} catch {
		// fall through to other error fields
	}
	return data.exception || data._error_message || null;
}
