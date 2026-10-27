// What an onboarding step's action does, as the desk onboarding widget does it. Every action is
// a hand-off to desk: a route, a form tour, a quick entry or a dialog over the page.

export function update_step(step, field, value = 1) {
	// a step done means the hooks set up for it are spent
	window.frappe.route_hooks = {};
	return window.frappe
		.xcall("frappe.desk.desktop.update_onboarding_step", { name: step.name, field, value })
		.then(() => (step[field] = value));
}

export function run_action(step) {
	const frappe = window.frappe;
	if (step.route_options && step.action !== "View Docs") {
		frappe.route_options = JSON.parse(step.route_options);
	}
	const actions = {
		"Create Entry": create_entry,
		"Show Form Tour": show_form_tour,
		"Update Settings": update_settings,
		"View Report": open_report,
		"Go to Page": go_to_page,
		"View Docs": view_docs,
		// the step is done when that module's own onboarding is, so opening it ticks nothing
		"Complete Onboarding": (step) => frappe.app.sidebar.open_module(get_shell(step.module)),
	};
	actions[step.action]?.(step);
}

export function import_records(step) {
	const frappe = window.frappe;
	frappe.require("data_import_tools.bundle.js", () => {
		frappe.data_import.open_data_import_dialog({
			reference_doctype: step.reference_document,
			import_type: "Insert New Records",
			on_close: () => refresh_step(step),
		});
	});
}

// A shell is keyed by its sidebar's name, which is not always its module's.
export function get_shell(module) {
	const shells = window.frappe.boot.module_sidebars || {};
	if (!module || shells[module]) return module;
	return Object.keys(shells).find((name) => shells[name].module === module);
}

function mark_complete(step, description) {
	return update_step(step, "is_complete").then(() => {
		window.frappe.ui.toast({
			message: window.__("Done: {0}", [step.title]),
			description: description && description !== step.title ? description : "",
			type: "success",
		});
	});
}

function complete_and_return(step, return_to) {
	return mark_complete(step).then(() => window.frappe.set_route(return_to));
}

function refresh_step(step) {
	if (step.is_complete) return;
	window.frappe
		.xcall("frappe.desk.doctype.onboarding_step.onboarding_step.get_onboarding_steps", {
			ob_steps: [{ step: step.name }],
		})
		.then(([fresh]) => fresh?.is_complete && mark_complete(step));
}

async function create_entry(step) {
	const frappe = window.frappe;
	if (step.is_complete) return frappe.set_route("List", step.reference_document);
	if (!step.show_full_form && !step.is_submittable) {
		frappe.ui.form.make_quick_entry(
			step.reference_document,
			() => mark_complete(step),
			null,
			null,
			true
		);
		return;
	}

	// a draft from the quick entry would not finish a step that needs a submit
	const return_to = frappe.get_route();
	const docname = await first_document(step.reference_document);
	const hooks = {};
	if (step.form_tour) {
		hooks.after_load = (frm) =>
			frm.tour.init({ tour_name: step.form_tour }).then(() => frm.tour.start());
	}
	if (step.is_submittable) {
		hooks.after_save = () =>
			frappe.ui.toast({
				message: window.__("Submit it to finish this step."),
				type: "info",
			});
		hooks.after_submit = () => complete_and_return(step, return_to);
	} else {
		hooks.after_save = () => complete_and_return(step, return_to);
	}
	set_route_hooks(step, hooks);
	frappe.set_route("Form", step.reference_document, docname);
}

function show_form_tour(step) {
	const frappe = window.frappe;
	const slug = frappe.router.slug(step.reference_document);
	const return_to = frappe.get_route();
	set_route_hooks(step, {
		after_load: (frm) => {
			const on_finish = () => complete_and_return(step, return_to);
			frm.tour.init({ tour_name: step.form_tour, on_finish }).then(() => frm.tour.start());
		},
	});
	frappe.set_route(step.is_single ? slug : `${slug}/new`);
}

function update_settings(step) {
	const frappe = window.frappe;
	const return_to = frappe.get_route();
	set_route_hooks(step, {
		after_load: (frm) => {
			frm.scroll_to_field(step.field);
			frm.doc.__unsaved = true;
		},
		after_save: () => complete_and_return(step, return_to),
	});
	frappe.set_route("Form", step.reference_document);
}

function open_report(step) {
	const frappe = window.frappe;
	const route = frappe.utils.generate_route({
		name: step.reference_report,
		type: "report",
		is_query_report: step.report_type !== "Report Builder",
		doctype: step.report_reference_doctype,
	});
	mark_complete(step, step.report_description).then(() => frappe.set_route(route));
}

function go_to_page(step) {
	mark_complete(step).then(() => {
		// a path outside the desk is a page load, not a route
		if (step.path.startsWith("/") && !step.path.startsWith("/desk")) {
			window.location.href = step.path;
		} else {
			window.frappe.set_route(step.path);
		}
	});
}

function view_docs(step) {
	window.open(step.path, "_blank", "noopener");
	mark_complete(step);
}

// `frappe.route_hooks` is one global the next form takes, whatever its doctype, so a hook that
// reaches another form puts itself back and waits for this step's form.
function set_route_hooks(step, hooks) {
	const frappe = window.frappe;
	frappe.route_hooks = {};
	for (const [event, callback] of Object.entries(hooks)) {
		const hook = (frm) => {
			if (frm?.doctype !== step.reference_document) {
				frappe.route_hooks[event] = hook;
				return;
			}
			callback(frm);
		};
		frappe.route_hooks[event] = hook;
	}
}

async function first_document(doctype) {
	const frappe = window.frappe;
	const { message } = await frappe.db.get_value("Form Tour", { reference_doctype: doctype }, [
		"first_document",
	]);
	if (message.first_document) {
		const rows = await frappe.db.get_list(doctype, { order_by: "creation" });
		if (rows?.length) return rows[0].name;
	}
	return "new";
}
