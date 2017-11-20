// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Social Login Key', {
	refresh: function(frm) {
		if(frappe.session.user !== "Administrator" || !frappe.boot.developer_mode) {
			if(frm.is_new()) {
				frm.set_value("custom", 1);
			}
			frm.toggle_enable("custom", 0);
			// make the document read-only
			for (var key of Object.keys(frm.fields_dict)) {
				if (frm.doc.custom_base_url && key == "base_url" ||
					["client_id", "client_secret"].includes(key)) {
					continue;
				} else {
					frm.toggle_enable(key, 0);
				}
			}
		}
	},

	custom: function(frm) {
		if (frm.doc.custom) frm.set_value("enable_social_login", 0);
	}
});
