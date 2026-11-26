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

// Labels looked up so far, so a record's fields show them as soon as it opens.
const knownLabels = new Map();

export function knownLabel(doctype, name) {
	return knownLabels.get(`${doctype}::${name}`);
}

// Labels for picked values, which a page of search results may leave out.
export async function labelLinks(doctype, names, referenceDoctype = null) {
	const rows = await call("frappe.desk.search.search_link", {
		doctype,
		txt: "",
		filters: { name: ["in", names] },
		reference_doctype: referenceDoctype,
		page_length: names.length,
	});
	const options = rows.map((row) => ({ value: row.value, label: row.label || row.value }));
	for (const option of options) knownLabels.set(`${doctype}::${option.value}`, option.label);
	return options;
}
