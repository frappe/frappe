// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("User Invitation", {
	onload(frm) {
		frappe.xcall("frappe.apps.get_apps").then((r) => {
			const apps = r?.map((r) => r.name) ?? [];
			frm.set_df_property("app_name", "options", ["frappe", ...apps]);
		});
	},
	refresh(frm) {
		if (frm.doc.status == "Pending") {
			frm.add_custom_button(__("Cancel"), () => {
				frappe.confirm(__("Are you sure you want to cancel the invitation?"), () =>
					frm.call("cancel_invite")
				);
			});
		}
	},
});
