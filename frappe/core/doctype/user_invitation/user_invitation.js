// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("User Invitation", {
	onload(frm) {
        frappe.xcall("frappe.apps.get_apps").then((r) => {
			const apps = r?.map((r) => r.name) ?? [];
			frm.set_df_property("app_name", "options", [" ", ...apps]);
		});
	}
});
