// Read-only data fetches over the desk's whitelisted client API.
function getList(doctype, options) {
	return frappe.xcall("frappe.client.get_list", { doctype, ...options });
}

export const loadAgents = () =>
	getList("AI Agent", { filters: { enabled: 1 }, fields: ["name", "title"], limit: 50 });

export const loadModels = () =>
	getList("AI Model", { filters: { enabled: 1 }, fields: ["name", "title"], limit: 50 });

export const loadHistory = () =>
	getList("AI Session", {
		filters: { owner: frappe.session.user },
		fields: ["name", "title", "creation"],
		order_by: "creation desc",
		limit: 15,
	});

export const searchSessions = (query) =>
	getList("AI Session", {
		filters: { owner: frappe.session.user, title: ["like", `%${query}%`] },
		fields: ["name", "title", "creation"],
		order_by: "creation desc",
		limit: 20,
	});

export const getSession = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "AI Session", name });

export const getPausedRun = (session) =>
	getList("AI Run", {
		filters: { session, status: "Paused" },
		fields: ["name", "questions"],
		order_by: "creation desc",
		limit: 1,
	});

// Fail any Running run left behind by a stream that was cut off (refresh/navigation),
// so a reloaded session isn't blocked from starting the next turn.
export const recoverSession = (session) => frappe.xcall("flow.api.recover_session", { session });

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
	if (!resp.ok) throw new Error(serverMessage(data) || `Upload failed (${resp.status})`);
	return data.message;
}

// Validate and stage an uploaded File for use as a chat attachment. Returns chip
// metadata; throws (unsupported type, unreadable, …) which surfaces on the chip.
export const attachFile = (file) => frappe.xcall("flow.api.attach_file", { file });

function serverMessage(data) {
	try {
		const msgs = JSON.parse(data._server_messages || "[]");
		if (msgs.length) return JSON.parse(msgs[0]).message;
	} catch {
		// fall through to other error fields
	}
	return data.exception || data._error_message || null;
}
