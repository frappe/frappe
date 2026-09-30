// The layouts the view-restore walk stores on its doctype and deletes: a Details form with one
// section closed by default in a later tab, and a Side Panel tall enough to scroll.

import { withRequest } from "./cachedScript.js";
import { BASE_URL, getMethod } from "./setup.js";

const DOCUMENTS = `${BASE_URL}/api/v2/document/Form%20Layout`;
const LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
// Matches every record, so the walk's rows win over a default row; marks them for deletion.
const MARKER = "doc.name != 'view-restore-walk'";
const PANEL_FIELDS = 24;
const MIN_ROWS = 3;

/** The navigation doctype with at least three rows whose later form tab has the most fields. */
export async function chooseDoctype(request, doctypes) {
	let best = null;
	for (const doctype of doctypes) {
		if (!(await hasRows(request, doctype))) continue;
		const plan = await planLayouts(request, doctype).catch(() => null);
		if (plan && (!best || plan.tabFields > best.plan.tabFields)) best = { doctype, plan };
	}
	if (!best)
		throw new Error(
			"No navigation doctype has three rows and a second form tab with a labelled section; set DOCTYPE."
		);
	return best.doctype;
}

/** Stores the walk's layouts and returns the form tab and the section the walk works with. */
export function storeViewLayouts(doctype) {
	return withRequest(async (request) => {
		await remove(request);
		const plan = await planLayouts(request, doctype);
		await insert(request, { dt: doctype, type: "Details", layout: plan.details });
		await insert(request, { dt: doctype, type: "Side Panel", layout: plan.panel });
		return { tab: plan.tab, section: plan.section };
	});
}

export function removeViewLayouts() {
	return withRequest(remove);
}

async function planLayouts(request, doctype) {
	const { layouts, fallback } = await getMethod(request, LAYOUTS, {
		dt: doctype,
		type: "Details",
	});
	const tabs = structuredClone(layouts.find((row) => !row.condition)?.layout ?? fallback);
	const later = tabs.slice(1).filter((tab) => tab.label && tab.sections.some((s) => s.label));
	if (!later.length)
		throw new Error(`${doctype} has no second form tab with a labelled section; set DOCTYPE.`);
	const tab = later.reduce((most, next) =>
		fieldsOf(next).length > fieldsOf(most).length ? next : most
	);
	const section = tab.sections.find((s) => s.label);
	Object.assign(section, { collapsible: true, opened: false });
	const others = tabs.filter((other) => other !== tab).flatMap(fieldsOf);
	const panel = [
		{
			name: "view_restore_walk",
			label: "View restore walk",
			columns: [{ name: "column_1", fields: others.slice(0, PANEL_FIELDS) }],
		},
	];
	return {
		tab: tab.label,
		section: section.label,
		tabFields: fieldsOf(tab).length,
		details: JSON.stringify(tabs),
		panel: JSON.stringify(panel),
	};
}

async function hasRows(request, doctype) {
	const url = `${BASE_URL}/api/v2/document/${encodeURIComponent(doctype)}`;
	const response = await request.get(url, { params: { limit: MIN_ROWS } });
	return response.ok() && (await response.json()).data.length >= MIN_ROWS;
}

async function insert(request, row) {
	const response = await request.post(DOCUMENTS, { data: { ...row, condition: MARKER } });
	if (!response.ok())
		throw new Error(`${row.type} Form Layout insert failed with ${response.status()}`);
}

async function remove(request) {
	const params = { filters: JSON.stringify([["condition", "=", MARKER]]), fields: '["name"]' };
	const found = await request.get(DOCUMENTS, { params });
	if (!found.ok()) throw new Error(`Form Layout read failed with ${found.status()}`);
	for (const { name } of (await found.json()).data ?? []) {
		const response = await request.delete(`${DOCUMENTS}/${name}`);
		if (!response.ok() && response.status() !== 404)
			throw new Error(`Form Layout delete failed with ${response.status()}`);
	}
}

function fieldsOf(tab) {
	return tab.sections.flatMap((section) => section.columns.flatMap((column) => column.fields));
}
