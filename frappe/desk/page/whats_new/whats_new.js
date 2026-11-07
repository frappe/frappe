frappe.pages["whats-new"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("What's New"),
		single_column: true,
	});

	frappe.xcall("frappe.utils.change_log.get_release_notes").then((release_notes) => {
		$(frappe.render_template("whats_new", { release_notes })).appendTo(page.body);
	});
};
