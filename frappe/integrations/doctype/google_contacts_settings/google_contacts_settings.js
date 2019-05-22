// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Contacts Settings', {
	refresh: function(frm) {
		if (frm.doc.enable) {
			frm.add_custom_button(__("Forward"), function() {
				frm.call('sync');
			});
		}
	},
});
