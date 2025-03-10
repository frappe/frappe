frappe.pages["m-navigation"].on_page_load = function (wrapper) {
	if (frappe.is_mobile()) {
		var page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "Home",
			single_column: true,
		});
		let sidebar = new frappe.ui.Sidebar();
		var element = $(".sidebar-items").detach();
		$(page.wrapper).append(element);
	}
};
