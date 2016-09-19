frappe.provide("frappe.integration_service")

frappe.integration_service.razorpay = {
	load: function(frm) {
		new frappe.integration_service.Razorpay(frm)
	},
	scheduler_job_helper: function(){
		return  {
			"Execute on every few minits of interval": "Take backup of database and files to dropbox on daily basis"
		}
	}
}

frappe.integration_service.Razorpay =  Class.extend({
	init:function(frm){
		this.frm = frm;
		this.frm.toggle_display("use_test_account", false);
		this.show_logs();
	},
	show_logs: function(){
		this.frm.add_custom_button(__("Show Log"), function(frm){
			frappe.route_options = {"integration_request_service": "Razorpay"};
			frappe.set_route("List", "Integration Request");
		}).addClass("btn-primary")
	}
})
	