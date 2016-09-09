frappe.provide("frappe.integration_service")

frappe.integration_service.dropbox_integration = {
	load: function(frm) {
		new frappe.integration_service.DropboxIntegration(frm)
	},
	scheduler_job_helper: function(){
		return  {
			"Daily": "Take backup of database and files to dropbox on daily basis",
			"Weekly": "Take backup of database and files to dropbox on weekly basis"
		}
	}
}

frappe.integration_service.DropboxIntegration = Class.extend({
	init: function(frm) {
		this.frm = frm;
		this.frm.toggle_display("use_test_account", false);
		if(this.frm.doc.service == "Dropbox Integration" && this.frm.doc.enabled && !this.frm.doc.__islocal){
			this.allow_dropbox_acess(frm);
			this.take_backup(frm);
		}
	},

	allow_dropbox_acess: function(frm) {
		this.frm.add_custom_button(__("Allow Dropbox Access"), function(frm){
			frappe.call({
				method: "frappe.integrations.dropbox_integration.get_dropbox_authorize_url",
				freeze: true,
				callback: function(r) {
					if(!r.exc) {
						window.open(r.message.url);
					}
				}
			})
		}).addClass("btn-primary")
	},

	take_backup: function(frm) {
		var me = this;
		this.frm.add_custom_button(__("Take Backup Now"), function(frm){
			frappe.call({
				method: "frappe.integrations.dropbox_integration.take_backup",
				freeze: true
			})
		}).addClass("btn-primary")
	}
})
