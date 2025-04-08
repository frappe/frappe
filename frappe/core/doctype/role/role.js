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

		frm.add_custom_button("Role Permissions Manager", function () {
			frappe.route_options = { role: frm.doc.name };
			frappe.set_route("permission-manager");
		});
		frm.add_custom_button("Show Users", function () {
			frappe.route_options = { role: frm.doc.name };
			frappe.set_route("List", "User", "Report");
		});

		if (!frm.is_new()) {
			frm.add_custom_button(__("Duplicate"), function() {
				let d = new frappe.ui.Dialog({
					title: __('Duplicate Role'),
					fields: [
						{
							label: __('New Role Name'),
							fieldname: 'new_role_name',
							fieldtype: 'Data',
							reqd: 1,
							default: frm.doc.role_name + ' Copy'
						}
					],
					primary_action_label: __('Create'),
					primary_action: function() {
						const new_role_name = d.get_value('new_role_name');
						
						frappe.call({
							method: "frappe.core.doctype.role.role.duplicate_role",
							args: {
								source_name: frm.doc.name,
								new_role_name: new_role_name
							},
							freeze: true,
							freeze_message: __("Creating duplicate role with permissions..."),
							callback: function(r) {
								if (r.message && r.message.name) {
									d.hide();
									frappe.set_route("Form", "Role", r.message.name);
								}
							}
						});
					}
				});
				
				d.show();
			});
		}
	}
});
