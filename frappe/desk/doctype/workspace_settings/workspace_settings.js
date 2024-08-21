// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workspace Settings", {
	setup(frm) {
		frm.hide_full_form_button = true;
		let workspace_visibilty = JSON.parse(frm.doc.workspace_visibility_json || "{}");

		// build fields from workspaces
		let options = frappe.boot.allowed_workspaces
		.filter((w) => w.public)
		.map((w) => {
				return {
					label: w.title,
					value: w.name,
					checked: workspace_visibilty[w.name] !== 0,
				};
			});

		// Define MultiCheck field for workspace visibility
		frm.docfields = [
			{
				fieldtype: "MultiCheck",
				fieldname: "workspace_visibility",
				options: options,
				select_all: true,
				columns: 2,
				sort_options: false,
			},
		];

		frappe.temp = frm;
	},
	validate(frm) {
		let selected_workspaces = frm.get_field("workspace_visibility").get_value() || [];
		let visibility = {};

		selected_workspaces.forEach((workspace) => {
			visibility[workspace] = 1;
		});

		frappe.boot.allowed_workspaces.forEach((workspace) => {
			if (!visibility[workspace.name] && workspace.public) {
				visibility[workspace.name] = 0;
			}
		});

		frm.doc.workspace_visibility_json = JSON.stringify(visibility);
		frm.doc.workspace_setup_completed = 1;
	},
	after_save(frm) {
		// reload page to show latest sidebar
		window.location.reload();
	},
	refresh(frm) {
		frm.dialog.set_alert(__("Select modules you want to see in the sidebar"));
	},
});
