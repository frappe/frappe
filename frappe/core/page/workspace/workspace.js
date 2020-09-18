frappe.pages['workspace'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		name: 'workspace',
		title: __("Workspace"),
	});

	frappe.workspace = new frappe.views.Workspace(wrapper);
	$(wrapper).bind('show', function () {
		frappe.workspace.show();
	});
}