frappe.pages["workflow-builder"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Workflow Builder"),
		single_column: true,
	});

	// hot reload in development
	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_workflow_builder(wrapper));
	}
};

frappe.pages["workflow-builder"].on_page_show = function (wrapper) {
	load_workflow_builder(wrapper);
};

function load_workflow_builder(wrapper) {
	let route = frappe.get_route();
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	if (route.length > 1) {
		frappe.require("workflow_builder.bundle.js").then(() => {
			frappe.workflow_builder = new frappe.ui.WorkflowBuilder({
				wrapper: $parent,
				page: wrapper.page,
				workflow: route[1],
			});
		});
	}
}
