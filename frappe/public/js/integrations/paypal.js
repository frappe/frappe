frappe.provide("frappe.integration_service")

frappe.integration_service.paypal = {
	load: function(frm) {
		new frappe.integration_service.PayPal(frm)
	}
}

frappe.integration_service.PayPal =  Class.extend({
	init:function(frm){
		this.frm = frm;
		this.show_logs();
	},
	show_logs: function(){
		this.frm.add_custom_button(__("Show Log"), function(frm){
			frappe.route_options = {"integration_request_service": "PayPal"};
			frappe.set_route("List", "Integration Request");
		}).addClass("btn-primary")
	}
})
	