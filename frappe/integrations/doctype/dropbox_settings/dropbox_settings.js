// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.provide("frappe.integration_service")

frappe.ui.form.on('Dropbox Settings', {
	refresh: function(frm) {
		frm.clear_custom_buttons();
		frm.events.take_backup(frm);
	},

	allow_dropbox_access: function(frm) {
		if ((frm.doc.app_access_key && frm.doc.app_secret_key) || frm.doc.dropbox_setup_via_site_config) {
			frappe.call({
				method: "frappe.integrations.doctype.dropbox_settings.dropbox_settings.get_dropbox_authorize_url",
				freeze: true,
				callback: function(r) {
					if(!r.exc) {
						frm.save();
						window.open(r.message.url);
					}
				}
			})
		}
		else {
			frappe.msgprint(__("Please enter values for App Access Key and App Secret Key"))
		}
	},

	take_backup: function(frm) {
		if (frm.doc.app_access_key && frm.doc.app_secret_key && frm.doc.dropbox_access_key && frm.doc.dropbox_access_secret) {
			frm.add_custom_button(__("Take Backup Now"), function(frm){
				frappe.call({
					method: "frappe.integrations.doctype.dropbox_settings.dropbox_settings.take_backup",
					freeze: true
				})
			}).addClass("btn-primary")
		}
	}
});

frappe.integration_service.dropbox_settings =  Class.extend({
	init: function(frm) {

	},

	get_scheduler_job_info: function() {
		return  {
			"Daily": "Take backup of database and files to dropbox on daily basis",
			"Weekly": "Take backup of database and files to dropbox on weekly basis"
		}
	},

	get_service_info: function(frm) {
		frappe.call({
			method: "frappe.integrations.doctype.dropbox_settings.dropbox_settings.get_service_details",
			callback: function(r){
				var integration_service_help = frm.fields_dict.integration_service_help.wrapper;
				$(integration_service_help).empty();
				$(integration_service_help).append(r.message);
			}
		})
	}
})
