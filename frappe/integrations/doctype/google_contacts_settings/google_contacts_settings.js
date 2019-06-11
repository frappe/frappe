// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Contacts Settings', {
	allow_contacts_access: function(frm) {
		frappe.call({
			method: "frappe.integrations.doctype.google_contacts.google_contacts.google_callback",
			callback: function(r) {
				if(!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	},
});
