import { reactive } from "vue";

import { call } from "../api/frappe.js";

const FILTERS = {
	User: { enabled: 1, user_type: "System User" },
	DocType: { istable: 0 },
};

// Labels from every search and lookup, by doctype and name: a pick keeps its label when later
// searches leave it out, and a record's fields show theirs as soon as it opens.
const labels = reactive(new Map());

export function knownLabel(doctype, name) {
	return labels.get(`${doctype}::${name}`);
}

// `search_link` answers DocType for everyone
export function canLabel(page, doctype) {
	return doctype === "DocType" || page.can(doctype, "select");
}

// a link's value, or a multi-link's, as the names it picks
export function pickedNames(value) {
	return Array.isArray(value) ? value : value ? [value] : [];
}

async function search(doctype, args) {
	const rows = await call("frappe.desk.search.search_link", { doctype, ...args });
	const options = rows.map((row) => ({ value: row.value, label: row.label || row.value }));
	for (const option of options) labels.set(`${doctype}::${option.value}`, option.label);
	return options;
}

// Use the same permission-aware search as Desk Link fields, across the whole doctype.
export function searchLinks(doctype, query = "", referenceDoctype = null) {
	return search(doctype, {
		txt: query,
		filters: FILTERS[doctype] ?? {},
		reference_doctype: referenceDoctype,
		page_length: 20,
	});
}

// Labels for picked values, which a page of search results may leave out.
export function labelLinks(doctype, names, referenceDoctype = null) {
	return search(doctype, {
		txt: "",
		filters: { name: ["in", names] },
		reference_doctype: referenceDoctype,
		page_length: names.length,
	});
}
