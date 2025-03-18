frappe.pages["m-navigation"].on_page_load = function (wrapper) {
	if (frappe.is_mobile()) {
		let page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "Home",
			single_column: true,
		});
		page.set_title(frappe.boot.app_data_map[frappe.current_app].app_title);
		let sidebar_items = $(".sidebar-items").detach();
		let apps_switcher = $(".app-switcher-menu").detach();
		$(page.wrapper).append(sidebar_items);
		$(page.wrapper).append(apps_switcher);
		sidebar_items.find(".standard-sidebar-item").each(function () {
			$(this).after("<hr>");
		});
		// app switcher
		let drop_icon = frappe.utils.icon("down");
		drop_icon = $(drop_icon).css("margin-left", "5px");
		$(page.$title_area.find(".title-text")).append(drop_icon);

		$(page.$title_area).on("click", () => {
			frappe.app.sidebar.apps_switcher.app_switcher_menu.toggleClass("hidden");
		});
	}
};
