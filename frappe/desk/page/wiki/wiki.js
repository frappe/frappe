frappe.provide('frappe.views')

frappe.pages['wiki'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		name: "Wiki",
		single_column: false,
	});

	frappe.wiki = new frappe.views.Wiki(wrapper);

	$(wrapper).bind('show', function () {
		frappe.wiki.show();
	});
}
