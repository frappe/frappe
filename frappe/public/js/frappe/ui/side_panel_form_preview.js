frappe.provide("frappe.ui");

// Mounts a real frappe.ui.form.Form into `body_el` for a faithful, read-only preview.
frappe.ui.render_side_panel_form_preview = function (body_el, doctype, docname, set_header) {
	return frappe.model.with_doctype(doctype).then(
		() =>
			new Promise((resolve, reject) => {
				frappe.model.with_doc(doctype, docname, () => {
					try {
						resolve(mount_form(body_el, doctype, docname, set_header));
					} catch (e) {
						reject(e);
					}
				});
			})
	);
};

function mount_form(body_el, doctype, docname, set_header) {
	const prev_cur_frm = window.cur_frm;
	const prev_pages = frappe.ui.pages;
	const prev_sidebar_attr = document.body.getAttribute("data-sidebar");
	const prev_title = document.title;

	frappe.ui.pages = {};

	let frm;
	try {
		frm = new frappe.ui.form.Form(doctype, body_el, true);
		frm.refresh(docname);
		frm.set_read_only();
	} finally {
		frappe.ui.pages = prev_pages;
		window.cur_frm = prev_cur_frm;
		if (prev_sidebar_attr === null) {
			document.body.removeAttribute("data-sidebar");
		} else {
			document.body.setAttribute("data-sidebar", prev_sidebar_attr);
		}
		frappe.breadcrumbs.update();
		document.title = prev_title;
	}

	// Toolbar already computed these onto frm.page during refresh() — read, don't recompute.
	if (set_header) {
		const indicator = frm.page.indicator.hasClass("hide")
			? null
			: [frm.page.indicator.text(), frm.page.indicator.attr("data-theme")];
		set_header({ title: frm.page.title, indicator });
	}

	// Runs the doctype's on_hide client-script trigger before the DOM is torn down.
	frm.side_panel_on_close = () => frm.$wrapper.trigger("hide");

	return frm;
}
