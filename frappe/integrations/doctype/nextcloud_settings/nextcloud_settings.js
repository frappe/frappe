// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('NextCloud Settings', {

	refresh: function(frm) {
		frm.clear_custom_buttons();
		frm.events.take_backup(frm);
	},

	enabled: function(frm) {
		frm.refresh();
	},

	take_backup: function(frm) {
		if (frm.doc.enabled && frm.doc.email && frm.doc.password) {
			frm.add_custom_button(__("Take Backup Now"), function() {
				frappe.call({
					method: "frappe.integrations.doctype.nextcloud_settings.nextcloud_settings.take_backup",
					freeze: true
				});
			}).addClass("btn-primary");
		}
	}
});
