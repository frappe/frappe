// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Contacts', {
	refresh: function(frm) {
		frm.set_value("user", frappe.session.user);

		if (frm.doc.refresh_token) {
			frm.add_custom_button(__('Sync Contacts'), function () {
				frappe.show_alert({
					indicator: 'green',
					message: __('Syncing')
				});
				frappe.call({
					method: "frappe.integrations.doctype.google_contacts.google_contacts.sync",
					args: {
						"g_contact": frm.doc.name
					},
				}).then((r) => {
					frappe.hide_progress();
					frappe.msgprint(__("{0}", [r.message]));
				});
			});
		}
	},
	authorize_google_contacts_access: function(frm) {
		console.log(frm.doc.name);
		frappe.call({
			method: "frappe.integrations.doctype.google_contacts.google_contacts.authorize_access",
			args: {
				"g_contact": frm.doc.name
			},
			callback: function(r) {
				if(!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	},
});
