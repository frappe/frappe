const FULL_HEIGHT_PAGE_CLASS = "full-height-page";

// the builder wants the canvas width, and the sidebar folds to its icon rail, so it
// arrives folded and is put back the way it was found on the way out. `on_page_show`
// runs again for every format opened without leaving the page, so the state is read
// once and kept until the matching hide.
let folded_sidebar = false;
let leaving_to = null;
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

frappe.pages["print-format-builder"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Print Format Builder"),
		single_column: true,
	});

	$(wrapper).on("hide", () => {
		document.body.classList.remove(FULL_HEIGHT_PAGE_CLASS);
		restore_sidebar_state();
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_print_format_builder(wrapper));
	}
};

frappe.pages["print-format-builder"].on_page_show = function (wrapper) {
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

function load_print_format_builder(wrapper) {
	let route = frappe.get_route();
	let $parent = $(wrapper).find(".layout-main-section");

	if (route.length < 2) {
		frappe.set_route("List", "Print Format");
		return;
	}

	const current = frappe.print_format_builder;
	if (current?.has_unsaved_changes?.() && route[1] !== leaving_to) {
		if (current.print_format === route[1]) return;
		const target = route[1];
		current.flush().then(
			() => {
				leaving_to = target;
				load_print_format_builder(wrapper);
			},
			() => {
				history.back();
				current.warn_unsaved(() => {
					leaving_to = target;
					frappe.set_route("print-format-builder", target);
				});
			}
		);
		return;
	}
	leaving_to = null;
	current?.destroy?.();
	$parent.empty();

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
