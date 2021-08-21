frappe.pages["print-format-builder-beta"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Print Format Builder"),
		single_column: true
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_print_format_builder_beta(wrapper));
	}
};

frappe.pages["print-format-builder-beta"].on_page_show = function(wrapper) {
	load_print_format_builder_beta(wrapper);
};

function load_print_format_builder_beta(wrapper) {
	let route = frappe.get_route();
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	if (route.length > 1) {
		frappe.require("print_format_builder.bundle.js").then(() => {
			frappe.print_format_builder = new frappe.ui.PrintFormatBuilder({
				wrapper: $parent,
				page: wrapper.page,
				print_format: route[1]
			});
		});
	} else {
		let d = new frappe.ui.Dialog({
			title: __("Select Print Format to edit"),
			fields: [
				{
					label: __("Print Format"),
					fieldname: "print_format",
					fieldtype: "Link",
					options: "Print Format",
					filters: {
						print_format_builder_beta: 1
					}
				}
			],
			primary_action({ print_format }) {
				if (!print_format) return;
				frappe.set_route("print-format-builder-beta", print_format);
			}
		});
		d.show();
	}
}
