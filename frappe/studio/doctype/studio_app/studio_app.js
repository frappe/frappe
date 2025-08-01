// Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Studio App", {
	refresh(frm) {
		frappe.xcall("frappe.core.doctype.module_def.module_def.get_installed_apps").then((r) => {
			const options = JSON.parse(r);
			options.unshift("");
			frm.set_df_property("frappe_app", "options", options);
		});

		if (!frappe.boot.developer_mode) {
			frm.set_df_property("is_standard", "read_only", 1);
			frm.set_df_property("frappe_app", "read_only", 1);
		}
	},
});
