frappe.pages['calendar'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Master Calendar',
		single_column: true
	});
}