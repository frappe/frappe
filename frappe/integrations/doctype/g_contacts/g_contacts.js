// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('G Contacts', {
	refresh: function(frm) {
		frm.set_value("user", frappe.session.user);

		if (frm.doc.enable && frm.doc.client_id && frm.doc.client_secret) {
			frm.add_custom_button(__('Sync Contacts'), function () {
				frappe.show_alert({
					indicator: 'green',
					message: __('Syncing')
				});
				frappe.call({
					method: "frappe.integrations.doctype.g_contacts.g_contacts.sync",
					args: {
						"doc": frm.doc.name
					},
				}).then((r) => {
					frappe.hide_progress();
					frappe.msgprint(__("{0}", [r.message]));
				});
			});
		}
	},
	allow_contacts_access: function(frm) {
		console.log(frm.doc.name);
		frappe.call({
			method: "frappe.integrations.doctype.g_contacts.g_contacts.authenticate_access",
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
