/**
 * frappe-ui POC page controller.
 *
 * Follows the same lazy-load pattern used by Workflow Builder and
 * Print Format Builder Beta: the page controller is thin and simply
 * calls frappe.require() for the heavy Vue bundle when the page is shown.
 */
frappe.pages["frappe-ui-poc"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("frappe-ui POC"),
		single_column: true,
	});

	// Hot-reload support in developer mode
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_frappe_ui_poc(wrapper));
	}
};

frappe.pages["frappe-ui-poc"].on_page_show = function (wrapper) {
	load_frappe_ui_poc(wrapper);
};

function load_frappe_ui_poc(wrapper) {
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	// Load the compiled CSS for the frappe-ui desk entry alongside the JS
	// bundle. frappe.require handles both extensions.
	frappe.require(["frappe_ui_poc.bundle.js", "frappe_ui_poc.bundle.css"]).then(() => {
		frappe.frappe_ui_poc = new frappe.ui.FrappeUIPoc({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
