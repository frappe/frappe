// Client tools run in the Desk window (the Flow panel is injected there) and return a
// JSON-serializable digest that flows back to the agent as the tool's result. The agent
// supplies only the tool name and arguments — it can never execute arbitrary browser code.

const LAYOUT_FIELDTYPES = new Set([
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Heading",
	"Fold",
	"Button",
]);

const registry = {
	read_screen: readScreen,
};

export async function runClientTool(name, args = {}) {
	const fn = registry[name];
	if (!fn) throw new Error(`Unknown client tool: ${name}`);
	return await fn(args);
}

function readScreen() {
	const route = typeof frappe?.get_route === "function" ? frappe.get_route() : [];
	const view = route[0] || "";
	const digest = { view, route };

	const frm = window.cur_frm;
	if (view === "Form" && frm?.doc) return { ...digest, ...formDigest(frm) };

	const list = window.cur_list;
	if (view === "List" && list) {
		digest.doctype = list.doctype;
		digest.list_view = route[2] || "List";
		digest.filters =
			typeof list.get_filters_for_args === "function" ? list.get_filters_for_args() : [];
		const selected =
			typeof list.get_checked_items === "function" ? list.get_checked_items(true) : [];
		if (selected.length) digest.selected = selected;
		return digest;
	}

	const report = frappe?.query_report;
	if (view === "query-report" && report) {
		digest.report = report.report_name;
		digest.filters =
			typeof report.get_filter_values === "function" ? report.get_filter_values() : {};
		return digest;
	}

	if (route[1]) digest.doctype = route[1];
	return digest;
}

function formDigest(frm) {
	const values = {};
	const missingMandatory = [];
	for (const df of frm.meta.fields) {
		if (LAYOUT_FIELDTYPES.has(df.fieldtype)) continue;
		const value = frm.doc[df.fieldname];
		const empty = value === undefined || value === null || value === "";
		if (df.reqd && empty) missingMandatory.push(df.fieldname);
		if (!empty && typeof value !== "object") values[df.fieldname] = value;
	}
	return {
		doctype: frm.doctype,
		name: frm.doc.name,
		is_new: Boolean(frm.is_new()),
		is_dirty: Boolean(frm.is_dirty()),
		docstatus: frm.doc.docstatus,
		values,
		missing_mandatory: missingMandatory,
	};
}
