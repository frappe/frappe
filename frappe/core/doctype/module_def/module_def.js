// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Module Def', {
	refresh: function(frm) {
		if (!frappe.boot.developer_mode) {
			frm.set_df_property("create_on_install", "read_only", 1);
		}
	}
});
