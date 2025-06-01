nts.pages["workflow-builder"].on_page_load = function (wrapper) {
	nts.ui.make_app_page({
		parent: wrapper,
		title: __("Workflow Builder"),
		single_column: true,
	});

	// hot reload in development
	if (nts.boot.developer_mode) {
		nts.hot_update = nts.hot_update || [];
		nts.hot_update.push(() => load_workflow_builder(wrapper));
	}
};

nts.pages["workflow-builder"].on_page_show = function (wrapper) {
	load_workflow_builder(wrapper);
};

function load_workflow_builder(wrapper) {
	let route = nts.get_route();
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	if (route.length > 1) {
		nts.require("workflow_builder.bundle.js").then(() => {
			nts.workflow_builder = new nts.ui.WorkflowBuilder({
				wrapper: $parent,
				page: wrapper.page,
				workflow: route[1],
			});
		});
	} else {
		let d = new nts.ui.Dialog({
			title: __("Create or Edit Workflow"),
			fields: [
				{
					label: __("Action"),
					fieldname: "action",
					fieldtype: "Select",
					options: [
						{ label: __("Create New"), value: "Create" },
						{ label: __("Edit Existing"), value: "Edit" },
					],
					change() {
						let action = d.get_value("action");
						d.get_primary_btn().text(action === "Create" ? __("Create") : __("Edit"));
					},
				},
				{
					label: __("Select Document Type"),
					fieldname: "doctype",
					fieldtype: "Link",
					options: "DocType",
					filters: {
						istable: 0,
					},
					reqd: 1,
					default: nts.route_options ? nts.route_options.doctype : null,
				},
				{
					label: __("New Workflow Name"),
					fieldname: "workflow_name",
					fieldtype: "Data",
					depends_on: (doc) => doc.action === "Create",
					mandatory_depends_on: (doc) => doc.action === "Create",
				},
				{
					label: __("Select Workflow"),
					fieldname: "workflow",
					fieldtype: "Link",
					options: "Workflow",
					only_select: 1,
					depends_on: (doc) => doc.action === "Edit",
					get_query() {
						return {
							filters: {
								document_type: d.get_value("doctype"),
							},
						};
					},
					mandatory_depends_on: (doc) => doc.action === "Edit",
				},
			],
			primary_action_label: __("Edit"),
			primary_action({ action, doctype, workflow, workflow_name }) {
				if (action === "Edit") {
					nts.set_route("workflow-builder", workflow);
				} else if (action === "Create") {
					d.get_primary_btn().prop("disabled", true);
					nts.db
						.insert({
							doctype: "Workflow",
							workflow_name: workflow_name,
							document_type: doctype,
						})
						.then((doc) => {
							nts.set_route("workflow-builder", doc.name);
						})
						.finally(() => {
							d.get_primary_btn().prop("disabled", false);
						});
				}
			},
		});
		d.set_value("action", "Create");
		d.show();
	}
}
