// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('G Contacts', {
	refresh: function(frm) {
		frm.set_value("user", frappe.session.user);
	},
	allow_contacts_access: function(frm) {
		frappe.call({
			method: "frappe.integrations.doctype.google_contacts.google_contacts.google_callback",
			args: {
				"doc": frm.doc.name
			},
			callback: function(r) {
				if(!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	}
});
