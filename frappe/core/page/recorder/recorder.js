frappe.pages['recorder'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Recorder',
		single_column: true
	});
}