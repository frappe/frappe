// Reuses generic client APIs — no custom backend. Activating a workflow via
// set_value runs Workflow.save(), whose controller deactivates the other workflows
// for the doctype (single active).
frappe.doctype_settings.register("workflow", function (panel, doctype) {
	// Edit opens the visual Workflow Builder (the deep tool) rather than the raw form.
	const open = (name) => {
		panel.dialog.hide();
		frappe.set_route("workflow-builder", name);
	};
	const create = () => {
		panel.dialog.hide();
		frappe.new_doc("Workflow", { document_type: doctype });
	};

	frappe.doctype_settings.render_list(panel, {
		title: __("Workflow"),
		description: __("Setup a multi-step workflow for {0}.", [doctype]),
		show_header: true,
		primary_action: { label: __("New"), icon: "plus", onclick: create },
		load: () =>
			frappe.db.get_list("Workflow", {
				filters: { document_type: doctype },
				fields: ["name", "workflow_name", "is_active"],
				order_by: "name asc",
				limit: 0,
			}),
		title_column: {
			label: __("Name"),
			primary: (r) => r.workflow_name || r.name,
			onclick: (r) => open(r.name),
			// Flag only the active workflow; inactive rows stay clean.
			tags: (r) => (r.is_active ? [{ label: __("Active"), color: "green" }] : []),
		},
		actions: (r) => [
			{
				label: r.is_active ? __("Disable") : __("Enable"),
				icon: r.is_active ? "ban" : "circle-check",
				onclick: (list) =>
					// Pass a dict so a 0 value isn't mistaken for "no value" by client.set_value.
					frappe.db
						.set_value("Workflow", r.name, { is_active: r.is_active ? 0 : 1 })
						.then(() => {
							frappe.show_alert({
								message: r.is_active ? __("Disabled") : __("Enabled"),
								indicator: "green",
							});
							list.reload();
						}),
			},
			{ label: __("Edit"), icon: "pencil", onclick: () => open(r.name) },
			{
				label: __("Delete"),
				icon: "trash-2",
				danger: true,
				onclick: (list) =>
					frappe.model.delete_doc("Workflow", r.name, () => {
						frappe.show_alert({ message: __("Deleted"), indicator: "green" });
						list.reload();
					}),
			},
		],
		empty_state: {
			icon: frappe.doctype_settings.tab_icon("workflow"),
			title: __("No Workflows found"),
			description: __("Create a workflow to control the states {0} moves through.", [
				doctype,
			]),
			action: { label: __("New Workflow"), onclick: create },
		},
	});
});
