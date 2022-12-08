frappe.pages["form-builder"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Form Builder"),
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
	if (route.length > 1) {
		let doctype = route[1];
		let is_customize_form = route[2] === "customize";

		if (frappe.form_builder?.doctype) {
			frappe.form_builder.doctype = frappe.form_builder.store.doctype = doctype;
			frappe.form_builder.customize = frappe.form_builder.store.is_customize_form =
				is_customize_form;
			frappe.form_builder.init(true);
			frappe.form_builder.store.fetch();
			return;
		}

		let $parent = $(wrapper).find(".layout-main-section");
		$parent.empty();

		frappe.require("form_builder.bundle.js").then(() => {
			frappe.form_builder = new frappe.ui.FormBuilder({
				wrapper: $parent,
				page: wrapper.page,
				doctype: doctype,
				customize: is_customize_form,
			});
		});
	}
}
