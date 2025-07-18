// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("User Invitation", {
	refresh(frm) {
		frappe.xcall("frappe.apps.get_apps").then((r) => {
			const apps = r?.map((r) => r.name) ?? [];
			const default_app = "frappe";
			frm.set_df_property("app_name", "options", [default_app, ...apps]);
			if (!frm.doc.app_name) {
				frm.set_value("app_name", default_app);
			}
		});
		if (frm.doc.__islocal || frm.doc.status !== "Pending") {
			return;
		}
		frm.add_custom_button(__("Cancel"), () => {
			frappe.confirm(__("Are you sure you want to cancel the invitation?"), () =>
				frm.call("cancel_invite")
			);
		});
	},
});
