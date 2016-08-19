frappe.provide("frappe.integration_service")

frappe.integration_service.dropbox_integration = {
	load: function(frm){
		new frappe.integration_service.DropboxIntegration(frm)
	}
}

frappe.integration_service.DropboxIntegration = Class.extend({
	init: function(frm){
		this.frm = frm;
		this.frm.toggle_display("use_test_account", false);
		this.allow_dropbox_acess(frm)
	},
	allow_dropbox_acess: function(frm){
		var me = this;
		
		if(this.frm.doc.service == "Dropbox Integration" && this.frm.doc.enabled && !this.frm.doc.__islocal){
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
		}
	}
})