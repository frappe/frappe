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

export const getSession = (name) =>
	frappe.xcall("frappe.client.get", { doctype: "AI Session", name });

export const getPausedRun = (session) =>
	getList("AI Run", {
		filters: { session, status: "Paused" },
		fields: ["name", "questions"],
		order_by: "creation desc",
		limit: 1,
	});
