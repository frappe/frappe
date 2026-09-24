const FULL_HEIGHT_PAGE_CLASS = "full-height-page";

let folded_sidebar = false;
let restore_sidebar = false;

function collapse_sidebar() {
	const sidebar = frappe.app?.sidebar;
	if (!sidebar || folded_sidebar) return;
	folded_sidebar = true;
	restore_sidebar = !!sidebar.sidebar_expanded;
	if (restore_sidebar) sidebar.close();
}

function restore_sidebar_state() {
	if (!folded_sidebar) return;
	folded_sidebar = false;
	if (!restore_sidebar) return;
	restore_sidebar = false;
	frappe.app?.sidebar?.open();
}

frappe.pages["print-format-builder-beta"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Print Format Builder"),
		single_column: true,
	});

	$(wrapper).on("hide", () => {
		document.body.classList.remove(FULL_HEIGHT_PAGE_CLASS);
		restore_sidebar_state();
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_print_format_builder(wrapper));
	}
};

frappe.pages["print-format-builder-beta"].on_page_show = function (wrapper) {
	document.body.classList.add(FULL_HEIGHT_PAGE_CLASS);
	collapse_sidebar();
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

function load_print_format_builder(wrapper, force = false) {
	let route = frappe.get_route();
	let $parent = $(wrapper).find(".layout-main-section");

	if (route.length < 2) {
		frappe.print_format_builder?.destroy?.();
		$parent.empty();
		frappe.set_route("List", "Print Format");
		return;
	}

	patch_breadcrumbs_once();
	frappe.breadcrumbs.add({
		type: "Custom",
		label: __("Print Format"),
		route: "/desk/print-format",
		_extra_label: route[1],
	});
	wrapper.page.set_title(route[1]);

	const current = frappe.print_format_builder;
	if (!force && current?.has_unsaved_changes?.()) {
		if (current.print_format === route[1]) return;
		current.leave(() => load_print_format_builder(wrapper, true));
		return;
	}
	current?.destroy?.();
	$parent.empty();

	frappe.require("print_format_builder.bundle.js").then(() => {
		frappe.print_format_builder = new frappe.ui.PrintFormatBuilder({
			wrapper: $parent,
			page: wrapper.page,
			print_format: route[1],
		});
	});
}
