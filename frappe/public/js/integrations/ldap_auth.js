frappe.provide("frappe.integration_service")

frappe.integration_service.ldap_auth = {
	load: function(frm) {
		new frappe.integration_service.ldapAuth(frm)
	}
}

frappe.integration_service.ldapAuth =  Class.extend({
	init:function(frm){
		this.frm = frm;
		this.frm.toggle_display("use_test_account", false);
	}
})
	