frappe.pages["print-format-builder"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Print Format Builder"),
		single_column: true,
		hide_sidebar: true,
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_print_format_builder(wrapper));
	}
};

frappe.pages["print-format-builder"].on_page_show = function (wrapper) {
	load_print_format_builder(wrapper);
};

function patch_breadcrumbs_once() {
	if (frappe.breadcrumbs._pfb_patched) return;
	frappe.breadcrumbs._pfb_patched = true;
	const orig = frappe.breadcrumbs.update.bind(frappe.breadcrumbs);
	frappe.breadcrumbs.update = function () {
		orig();
		const crumbs = this.all[this.current_page()];
		if (crumbs?._extra_label) {
			this.append_breadcrumb_element("", crumbs._extra_label);
		}
	};
}

function load_print_format_builder(wrapper) {
	let route = frappe.get_route();
	let $parent = $(wrapper).find(".layout-main-section");
	frappe.print_format_builder?.destroy?.();
	$parent.empty();

	if (route.length < 2) {
		frappe.set_route("List", "Print Format");
		return;
	}

	// _extra_label is re-appended on every breadcrumbs.update() call so it survives route changes
	patch_breadcrumbs_once();
	frappe.breadcrumbs.add({
		type: "Custom",
		label: __("Print Format"),
		route: "/desk/print-format",
		_extra_label: route[1],
	});
	wrapper.page.set_title(route[1]);

	frappe.require("print_format_builder.bundle.js").then(() => {
		frappe.print_format_builder = new frappe.ui.PrintFormatBuilder({
			wrapper: $parent,
			page: wrapper.page,
			print_format: route[1],
		});
	});
}
