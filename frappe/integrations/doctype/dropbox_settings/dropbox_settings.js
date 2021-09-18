// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dropbox Settings', {
	refresh: function(frm) {
		frm.toggle_display(["app_access_key", "app_secret_key"], !(frm.doc.__onload && frm.doc.__onload.dropbox_setup_via_site_config));
		frm.clear_custom_buttons();
		frm.events.take_backup(frm);
	},

	allow_dropbox_access: function(frm) {
		if (frm.doc.app_access_key && frm.doc.app_secret_key) {
			frappe.call({
				method: "frappe.integrations.doctype.dropbox_settings.dropbox_settings.get_dropbox_authorize_url",
				freeze: true,
				callback: function(r) {
					if(!r.exc) {
						window.open(r.message.auth_url);
					}
				}
			})
		}
		else if (frm.doc.__onload && frm.doc.__onload.dropbox_setup_via_site_config) {
			frappe.call({
				method: "frappe.integrations.doctype.dropbox_settings.dropbox_settings.get_redirect_url",
				freeze: true,
				callback: function(r) {
					if(!r.exc) {
						window.open(r.message.auth_url);
					}
				}
			})
		}
		else {
			frappe.msgprint(__("Please enter values for App Access Key and App Secret Key"))
		}
	},

	take_backup: function(frm) {
		if (frm.doc.enabled && ((frm.doc.app_access_key && frm.doc.app_secret_key)
			|| (frm.doc.__onload && frm.doc.__onload.dropbox_setup_via_site_config))) {
			frm.add_custom_button(__("Take Backup Now"), function(frm){
				frappe.call({
					method: "frappe.integrations.doctype.dropbox_settings.dropbox_settings.take_backup",
					freeze: true
				})
			}).addClass("btn-primary")
		}
	}
});

