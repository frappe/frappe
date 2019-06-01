// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Contacts', {
	refresh: function(frm) {
		if (frm.doc.enable && frm.doc.client_id && frm.doc.client_secret) {
			frm.add_custom_button(__('Sync Contacts'), function () {
				if (frm.doc.access_authorised) {
					frappe.show_alert({
						indicator: 'green',
						message: __('Syncing')
					});
					frappe.call({
						method: "frappe.integrations.doctype.google_contacts.google_contacts.sync",
						callback: function() {
							frappe.hide_progress();
							frappe.msgprint(__("Google Contacts Synced."));
						}
					});
				} else {
					frappe.throw("Allow Contacts Access for Syncing.");
				}
			});
		}
	},
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
	}
});
