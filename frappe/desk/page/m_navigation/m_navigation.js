frappe.pages["m-navigation"].on_page_load = function (wrapper) {
	if (frappe.is_mobile()) {
		let page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "Home",
			single_column: true,
		});
		page.set_title(frappe.boot.app_data_map[frappe.current_app].app_title);
		let sidebar = new frappe.ui.Sidebar();
		let sidebar_items = $(".sidebar-items").detach();
		$(page.wrapper).append(sidebar_items);
		// sidebar_items.find(".sidebar-item-control").each(function() {
		// 	let control = $(this)
		// 	let item = $($(this).siblings()[0])
		// 	control.detach();
		// 	item.append(control);
		// });
		// sidebar_items.find(".item-anchor").each(function(){
		// 	console.log(this)

		// 	let div = document.createElement("div")
		// 	$(this).append(div)
		// 	let last_child = $($(this).children()[3])
		// 	let first_child = $($(this).children()[0])
		// 	$(this).children().each(function(){
		// 		if (this == last_child[0] || this == first_child[0]) return
		// 		last_child.append(this)
		// 	})
		// })
		sidebar_items.find(".standard-sidebar-item").each(function () {
			$(this).after("<hr>");
		});
	}
};
