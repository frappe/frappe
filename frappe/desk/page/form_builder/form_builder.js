frappe.pages["form-builder"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Form Builder",
		single_column: true,
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_form_builder(wrapper));
	}
};

frappe.pages["form-builder"].on_page_show = function (wrapper) {
	load_form_builder(wrapper);
};

function load_form_builder(wrapper) {
	let route = frappe.get_route();
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	frappe.require("form_builder.bundle.js").then(() => {
		frappe.form_builder = new frappe.ui.FormBuilder({
			wrapper: $parent,
			page: wrapper.page,
			doctype: route[1],
		});
	});
}
