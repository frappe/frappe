/**
 * frappe-ui POC page controller.
 *
 * Thin wrapper that loads the Vue island bundle on first visit and lets
 * `mountVueIsland` (called from inside the bundle) handle the mount,
 * portal, router, theme attrs, and hot reload.
 */
frappe.pages["frappe-ui-poc"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("frappe-ui POC"),
		single_column: true,
	});
};

frappe.pages["frappe-ui-poc"].on_page_show = function (wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	// Only the JS is loaded here. The island's CSS is injected into its shadow
	// root by mountVueIsland (styleBundles), not into the document <head>.
	frappe.require(["frappe_ui_poc.bundle.js"]).then(() => {
		frappe.ui.FrappeUIPoc({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
};
