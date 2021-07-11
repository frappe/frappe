frappe.pages["print-format-builder-beta"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Print Format Builder"),
		single_column: true
	});

	function load_print_format_builder_beta() {
		let route = frappe.get_route();
		let $parent = $(wrapper).find(".layout-main-section");
		$parent.empty();

		if (route.length > 1) {
			frappe.require("print_format_builder.bundle.js").then(() => {
				frappe.print_format_builder = new frappe.ui.PrintFormatBuilder({
					wrapper: $parent,
					page,
					print_format: route[1]
				});
			});
		}
	}

	load_print_format_builder_beta();

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(load_print_format_builder_beta);
	}
};
