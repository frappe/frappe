// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings["User"] = {
	add_fields: ["enabled", "user_type", "user_image"],
	filters: [["enabled", "=", 1]],
	onload(listview) {
		this.set_default_app_options(listview);
		this.add_bulk_role_actions(listview);
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
	add_bulk_role_actions(listview) {
		const open_role_dialog = ({ title, get_action_label, method, destructive }) => {
			const users = listview.get_checked_items(true);
			if (!users.length) {
				frappe.msgprint(__("Select records to update roles"));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: title,
				fields: [
					{
						fieldtype: "TableMultiSelect",
						fieldname: "roles",
						label: __("Roles"),
						reqd: 1,
						options: "Has Role",
					},
				],
				primary_action_label: get_action_label(users.length),
				primary_action(values) {
					const roles = (values.roles || []).map((r) => r.role).filter(Boolean);
					if (!roles.length) return;

					dialog.disable_primary_action();
					frappe.call({
						method: method,
						args: { users, roles },
						freeze: true,
						callback() {
							dialog.hide();
							listview.clear_checked_items();
							listview.refresh();
						},
						error() {
							dialog.enable_primary_action();
						},
					});
				},
			});

			if (destructive) {
				dialog.get_primary_btn().attr("data-theme", "red");
			}

			dialog.show();
		};

		listview.page.add_actions_menu_item(__("Add Roles"), () =>
			open_role_dialog({
				title: __("Add Roles"),
				get_action_label: (count) => __("Add to {0} Users", [count]),
				method: "frappe.core.doctype.user.user.bulk_add_roles",
			})
		);

		listview.page.add_actions_menu_item(__("Remove Roles"), () =>
			open_role_dialog({
				title: __("Remove Roles"),
				get_action_label: (count) => __("Remove from {0} Users", [count]),
				method: "frappe.core.doctype.user.user.bulk_remove_roles",
				destructive: true,
			})
		);
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
