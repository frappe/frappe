import { reactive } from "vue";

import { call } from "../api/frappe.js";

const FILTERS = {
	User: { enabled: 1, user_type: "System User" },
	DocType: { istable: 0 },
};

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
	return rows.map((row) => ({ value: row.value, label: row.label || row.value }));
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
function labelLinks(doctype, names, referenceDoctype = null) {
	return search(doctype, {
		txt: "",
		filters: { name: ["in", names] },
		reference_doctype: referenceDoctype,
		page_length: names.length,
	});
}

// The labels a view's searches and lookups found, by doctype and name, for as long as the view
// is open: a pick keeps its label when later searches leave it out, and a record's fields show
// theirs as soon as it opens.
export function linkLabels() {
	const known = reactive(new Map());
	const keep = (doctype) => (options) => {
		for (const option of options) known.set(`${doctype}::${option.value}`, option.label);
		return options;
	};
	return {
		get: (doctype, name) => known.get(`${doctype}::${name}`),
		search: (doctype, query, referenceDoctype) =>
			searchLinks(doctype, query, referenceDoctype).then(keep(doctype)),
		label: (doctype, names, referenceDoctype) =>
			labelLinks(doctype, names, referenceDoctype).then(keep(doctype)),
	};
}
