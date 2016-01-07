frappe.pages['backups'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Download Backups',
		single_column: true
	});

	frappe.breadcrumbs.add("Setup");

	$(frappe.render_template("backups")).appendTo(page.body.addClass("no-border"));
}
