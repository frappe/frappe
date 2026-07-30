frappe.provide("frappe.ui");

let original_cur_frm;
let owns_cur_frm = false;

function take_over_cur_frm(frm) {
	if (!owns_cur_frm) {
		original_cur_frm = window.cur_frm;
		owns_cur_frm = true;
	}
	window.cur_frm = frm;
}

function release_cur_frm(frm) {
	if (!owns_cur_frm || (frm && window.cur_frm !== frm)) return;
	window.cur_frm = original_cur_frm;
	owns_cur_frm = false;
}

let script_manager_patched = false;

function ensure_script_manager_patched() {
	if (script_manager_patched) return;
	script_manager_patched = true;
	const ScriptManager = frappe.ui.form.ScriptManager;
	const original_trigger = ScriptManager.prototype.trigger;
	ScriptManager.prototype.trigger = function (...args) {
		if (this.frm.__side_panel_preview) {
			return Promise.resolve();
		}
		return original_trigger.apply(this, args);
	};
}

let form_patched = false;

function ensure_form_patched() {
	if (form_patched) return;
	form_patched = true;
	const Form = frappe.ui.form.Form;
	const original_watch_model_updates = Form.prototype.watch_model_updates;
	Form.prototype.watch_model_updates = function (...args) {
		if (this.__side_panel_preview) return;
		return original_watch_model_updates.apply(this, args);
	};
}

frappe.ui.render_side_panel_form_preview = function (
	body_el,
	doctype,
	docname,
	set_header,
	previous,
	is_current
) {
	return frappe.model.with_doctype(doctype).then(
		() =>
			new Promise((resolve, reject) => {
				frappe.model.with_doc(doctype, docname, () => {
					// with_doctype/with_doc are async — a newer open()/close() may have
					// superseded us meanwhile. Bail before mounting.
					if (is_current && !is_current()) {
						resolve(null);
						return;
					}
					try {
						resolve(mount_form(body_el, doctype, docname, set_header, previous));
					} catch (e) {
						reject(e);
					}
				});
			})
	);
};

function mount_form(body_el, doctype, docname, set_header, previous) {
	const reuse =
		previous instanceof frappe.ui.form.Form &&
		previous.doctype === doctype &&
		!previous.__side_panel_closed;

	if (previous instanceof frappe.ui.form.Form && !reuse) {
		previous.side_panel_on_close();
	}

	const frm = reuse ? refresh_form(previous, docname) : new_form(body_el, doctype, docname);

	apply_header(frm, set_header);
	return frm;
}

function make_close_handler(frm) {
	return () => {
		if (frm.__side_panel_closed) return;
		frm.__side_panel_closed = true;

		frm.__side_panel_wrapper_el?.remove();
		try {
			frm.$wrapper.trigger("hide");
		} catch (e) {
			console.error("[side panel preview] error tearing down preview form", e);
		}
		frappe.realtime.doc_unsubscribe(frm.doctype, frm.docname);
		release_cur_frm(frm);
	};
}

function new_form(body_el, doctype, docname) {
	ensure_script_manager_patched();
	ensure_form_patched();

	const wrapper_el = document.createElement("div");
	body_el.appendChild(wrapper_el);

	const frm = with_global_state_snapshot(() => {
		const frm = new frappe.ui.form.Form(doctype, wrapper_el, true);
		frm.__side_panel_preview = true;
		frm.__side_panel_wrapper_el = wrapper_el;
		take_over_cur_frm(frm);
		frm.refresh(docname);
		frm.set_read_only();
		return frm;
	});

	frm.side_panel_on_close = make_close_handler(frm);
	return frm;
}

function refresh_form(frm, docname) {
	const previous_docname = frm.docname;

	return with_global_state_snapshot(() => {
		take_over_cur_frm(frm);
		frm.refresh(docname);
		frm.set_read_only();
		if (previous_docname && previous_docname !== docname) {
			frappe.realtime.doc_unsubscribe(frm.doctype, previous_docname);
		}
		return frm;
	});
}

function with_global_state_snapshot(fn) {
	const prev_pages = frappe.ui.pages;
	const prev_sidebar_attr = document.body.getAttribute("data-sidebar");
	const prev_title = document.title;

	frappe.ui.pages = {};
	try {
		return fn();
	} finally {
		frappe.ui.pages = prev_pages;
		if (prev_sidebar_attr === null) {
			document.body.removeAttribute("data-sidebar");
		} else {
			document.body.setAttribute("data-sidebar", prev_sidebar_attr);
		}
		frappe.breadcrumbs.update();
		document.title = prev_title;
	}
}

function apply_header(frm, set_header) {
	if (!set_header) return;
	const indicator = frm.page.indicator.hasClass("hide")
		? null
		: [frm.page.indicator.text(), frm.page.indicator.attr("data-theme")];
	set_header({ title: frm.page.title, indicator });
}
