// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Social Login Key', {
	refresh: function(frm) {
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);

		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.disable_save();
		}
	}
});
