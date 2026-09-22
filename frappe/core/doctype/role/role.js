// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See LICENSE

frappe.ui.form.on("Role", {
	refresh: function (frm) {
		if (frm.doc.name === "All") {
			frm.dashboard.add_comment(
				__("Role 'All' will be given to all system + website users."),
				"yellow"
			);
		} else if (frm.doc.name === "Desk User") {
			frm.dashboard.add_comment(
				__("Role 'Desk User' will be given to all system users."),
				"yellow"
			);
		}

		frm.set_df_property("is_custom", "read_only", frappe.session.user !== "Administrator");

		frm.add_custom_button(
			__("Role Permissions Manager"),
			function () {
				frappe.route_options = { role: frm.doc.name };
				frappe.set_route("permission-manager");
			},
			__("View")
		);

		frm.add_custom_button(
			__("Show Users"),
			function () {
				frappe.route_options = { role: frm.doc.name };
				frappe.set_route("List", "User", "Report");
			},
			__("View")
		);

		if (frappe.user.has_role("System Manager")) {
			frm.add_custom_button(
				__("Replicate Role"),
				function () {
					replicate_role(frm);
				},
				__("Action")
			);
		}
	},
});

function replicate_role(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Replicate Role"),
		fields: [
			{
				label: __("New Role Name"),
				fieldname: "new_role_name",
				fieldtype: "Data",
				default: frm.doc.name,
				reqd: 1,
			},
		],
		freeze: true,
		freeze_message: __("Replicating Role..."),
		primary_action_label: __("Replicate"),
		primary_action: function (values) {
			dialog.hide();
			frappe.call({
				method: "replicate_role",
				doc: frm.doc,
				args: {
					cur_role: frm.doc.name,
					new_role: values.new_role_name,
				},
				callback: function (r) {
					if (r.message) {
						frappe.set_route("Form", "Role", r.message);
						frappe.show_alert({
							message: __("New role created successfully."),
							indicator: "green",
						});
					} else if (r.exc) {
						JSON.parse(r.exc).forEach((err) => {
							frappe.show_alert({
								message: __(err),
								indicator: "red",
							});
						});
					}
				},
			});
		},
	});
	dialog.show();
}
