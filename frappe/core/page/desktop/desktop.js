frappe.pages['desktop'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Desktop',
		single_column: true
	});
}