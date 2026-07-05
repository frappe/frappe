// Client tools run in the Desk window (the Flow panel is injected there) and return a
// JSON-serializable result that flows back to the agent. The agent supplies only the tool
// name and arguments — it can never execute arbitrary browser code.

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
	navigate: navigate,
	fill: fill,
	act: act,
};

export async function runClientTool(name, args = {}) {
	const fn = registry[name];
	if (!fn) throw new Error(`Unknown client tool: ${name}`);
	return await fn(args);
}

async function navigate({ view, doctype, name, report, workspace, filters }) {
	if (view === "new") {
		if (!doctype) throw new Error("view 'new' needs a doctype");
		const newName = await openNewForm(doctype);
		return { navigated: true, route: ["Form", doctype, newName] };
	}

	let route;
	if (view === "form") {
		if (!doctype || !name) throw new Error("view 'form' needs a doctype and name");
		route = ["Form", doctype, name];
	} else if (view === "list") {
		if (!doctype) throw new Error("view 'list' needs a doctype");
		route = ["List", doctype];
	} else if (view === "report") {
		if (!report) throw new Error("view 'report' needs a report");
		route = ["query-report", report];
	} else if (view === "workspace") {
		if (!workspace) throw new Error("view 'workspace' needs a workspace");
		route = ["Workspaces", workspace];
	} else {
		throw new Error(`Unknown view: ${view}`);
	}

	if (filters && (view === "list" || view === "report")) frappe.route_options = filters;
	await frappe.set_route(route);
	return { navigated: true, route };
}

// Open a blank *full* form, bypassing the Quick Entry modal that frappe.new_doc opens for some
// doctypes
function openNewForm(doctype) {
	return new Promise((resolve, reject) => {
		frappe.model.with_doctype(doctype, () => {
			try {
				const doc = frappe.model.get_new_doc(doctype);
				frappe.set_route("Form", doctype, doc.name).then(() => resolve(doc.name));
			} catch (e) {
				reject(e);
			}
		});
	});
}

async function fill({ values }) {
	const frm = window.cur_frm;
	if (!frm?.doc) throw new Error("no form is open to fill");
	if (!values || typeof values !== "object") {
		throw new Error("values must be an object of {fieldname: value}");
	}

	const known = new Set(frm.meta.fields.map((df) => df.fieldname));
	const toSet = {};
	const errors = {};
	for (const [field, value] of Object.entries(values)) {
		if (known.has(field)) toSet[field] = value;
		else errors[field] = "no such field on this doctype";
	}

	const fields = Object.keys(toSet);
	if (fields.length) {
		await frm.set_value(toSet);
		if (typeof frm.scroll_to_field === "function") frm.scroll_to_field(fields[0]);
	}

	const state = formState(frm);
	if (Object.keys(errors).length) state.errors = errors;
	return state;
}

async function act({ action }) {
	const frm = window.cur_frm;
	if (!frm?.doc) throw new Error("no form is open to act on");
	if (!action) throw new Error("action is required");

	const lifecycle = { save: "Save", submit: "Submit", cancel: "Cancel" };
	if (lifecycle[action]) {
		await frm.save(lifecycle[action]);
	} else {
		const doc = await frappe.xcall("frappe.model.workflow.apply_workflow", {
			doc: frm.doc,
			action,
		});
		frappe.model.sync(doc);
		await frm.refresh();
	}
	return formState(frm);
}

function readScreen() {
	const route = typeof frappe?.get_route === "function" ? frappe.get_route() : [];
	const view = route[0] || "";
	const screen = { view, route };

	const frm = window.cur_frm;
	if (view === "Form" && frm?.doc) return { ...screen, ...formState(frm) };

	const list = window.cur_list;
	if (view === "List" && list) {
		screen.doctype = list.doctype;
		screen.list_view = route[2] || "List";
		screen.filters =
			typeof list.get_filters_for_args === "function" ? list.get_filters_for_args() : [];
		const selected =
			typeof list.get_checked_items === "function" ? list.get_checked_items(true) : [];
		if (selected.length) screen.selected = selected;
		return screen;
	}

	const report = frappe?.query_report;
	if (view === "query-report" && report) {
		screen.report = report.report_name;
		screen.filters =
			typeof report.get_filter_values === "function" ? report.get_filter_values() : {};
		return screen;
	}

	if (route[1]) screen.doctype = route[1];
	return screen;
}

function formState(frm) {
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
		is_submittable: Boolean(frm.meta.is_submittable),
		docstatus: frm.doc.docstatus,
		values,
		missing_mandatory: missingMandatory,
	};
}
