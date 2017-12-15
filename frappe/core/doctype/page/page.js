// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Page', {
	refresh: function(frm) {
		if(!frappe.boot.developer_mode && user != 'Administrator') {
			// make the document read-only
			frm.set_read_only();
		}
	}
});
