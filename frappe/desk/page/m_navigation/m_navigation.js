frappe.pages["m-navigation"].on_page_load = function (wrapper) {
	if (frappe.is_mobile()) {
		let page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "Home",
			single_column: true,
		});
		page.set_title(frappe.boot.app_data_map[frappe.current_app].app_title);
		let sidebar_items = $(".sidebar-items").detach();
		$(page.wrapper).append(sidebar_items);
		sidebar_items.find(".standard-sidebar-item").each(function () {
			$(this).after("<hr>");
		});
	}
};
