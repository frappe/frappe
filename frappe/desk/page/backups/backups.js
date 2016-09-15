frappe.pages['backups'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Download Backups',
		single_column: true
	});

  page.add_inner_button(__("Set Number of Backups"), function() {
		frappe.set_route('Form', 'System Settings');
	});

	frappe.breadcrumbs.add("Setup");

	$(frappe.render_template("backups")).appendTo(page.body.addClass("no-border"));
}
