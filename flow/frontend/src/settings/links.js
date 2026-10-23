import { call } from "../api/frappe.js";

const FILTERS = {
	User: { enabled: 1, user_type: "System User" },
	DocType: { istable: 0 },
};

// Use the same permission-aware search as Desk Link fields, across the whole doctype.
export async function searchLinks(doctype, query = "", referenceDoctype = null) {
	const rows = await call("frappe.desk.search.search_link", {
		doctype,
		txt: query,
		filters: FILTERS[doctype] ?? {},
		reference_doctype: referenceDoctype,
		page_length: 20,
	});
	return rows.map((row) => ({ value: row.value, label: row.label || row.value }));
}
