// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings["User"] = {
	add_fields: ["enabled", "user_type", "user_image"],
	filters: [["enabled", "=", 1]],
	onload(listview) {
		this.set_default_app_options(listview);

		listview.page.add_actions_menu_item(__("Add Roles"), () => {
			const selected_users = listview.get_checked_items(true);
			if (!selected_users.length) {
				frappe.msgprint(__("Please select at least one user."));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __("Add Roles"),
				fields: [
					{
						fieldtype: "TableMultiSelect",
						fieldname: "roles",
						label: __("Roles"),
						reqd: 1,
						options: "Has Role",
					},
				],
				primary_action_label: __("Add"),
				primary_action(values) {
					if (!values.roles?.length) return;
					const roles = values.roles.map((r) => r.role).filter(Boolean);
					frappe.call({
						method: "frappe.core.doctype.user.user.bulk_add_roles",
						args: { users: selected_users, roles: roles },
						freeze: true,
						callback() {
							dialog.hide();
							listview.refresh();
							frappe.show_alert(__("Roles added successfully"));
						},
					});
				},
			});
			dialog.show();
		});
	},
	prepare_data: function (data) {
		data["user_for_avatar"] = data["name"];
	},
	get_indicator: function (doc) {
		if (doc.enabled) {
			return [__("Active"), "green", "enabled,=,1"];
		} else {
			return [__("Disabled"), "gray", "enabled,=,0"];
		}
	},
	set_default_app_options(listview) {
		const default_app_field = frappe.meta.get_docfield("User", "default_app");
		if (!default_app_field) return;

		frappe.xcall("frappe.apps.get_apps").then((r) => {
			let apps = r?.map((r) => r.name) || [];
			default_app_field.options = ["", ...apps].join("\n");
		});
	},
};

frappe.help.youtube_id["User"] = "8Slw1hsTmUI";
