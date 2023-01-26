// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Notification Settings", {
	onload: (frm) => {
		frappe.breadcrumbs.add({
			label: __("Settings"),
			route: "#modules/Settings",
			type: "Custom",
		});
		frm.set_query("subscribed_documents", () => {
			return {
				filters: {
					istable: 0,
				},
			};
		});
	},

	refresh: (frm) => {
		if (frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Go to Notification Settings List"), () => {
				frappe.set_route("List", "Notification Settings");
			});
		}
	},
});
