// Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Studio App", {
	refresh(frm) {
		frappe.xcall("frappe.core.doctype.module_def.module_def.get_installed_apps").then((r) => {
			frm.set_df_property("frappe_app", "options", JSON.parse(r));
			if (!frm.doc.frappe_app) {
				frm.set_value("frappe_app", "frappe");
			}
		});

		if (!frappe.boot.developer_mode) {
			frm.set_df_property("is_standard", "read_only", 1);
		}
	},
});
