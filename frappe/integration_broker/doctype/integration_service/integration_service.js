// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.provide("frappe.integration_service");

{% include 'frappe/integrations/doctype/razorpay_settings/razorpay_settings.js' %}
{% include 'frappe/integrations/doctype/paypal_settings/paypal_settings.js' %}
{% include 'frappe/integrations/doctype/dropbox_settings/dropbox_settings.js' %}
{% include 'frappe/integrations/doctype/ldap_settings/ldap_settings.js' %}

frappe.ui.form.on('Integration Service', {
	onload: function(frm) {
		frappe.call({
			method: "frappe.integration_broker.doctype.integration_service.integration_service.get_integration_services",
			callback: function(r){
				set_field_options("service", r.message)
			}
		})
	},

	refresh: function(frm){
		if (frm.doc.service){
			frm.events.setup_custom_buttons(frm);
			frm.events.setup_service_details(frm);
		}
	},
	
	service: function(frm){
		frm.events.setup_custom_buttons(frm);
		frm.events.setup_service_details(frm);
	},
	
	setup_custom_buttons: function(frm) {
		frm.clear_custom_buttons();

		frm.add_custom_button(__("{0} Settings", [frm.doc.service]), function(){
			frappe.set_route("List", frm.doc.service + " Settings");
		});

		frm.add_custom_button(__("Show Log"), function(){
			frappe.route_options = {"integration_request_service": frm.doc.service};
			frappe.set_route("List", "Integration Request");
		});
	},
	
	setup_service_details: function(frm) {
		var service_name =  frm.doc.service.toLowerCase().replace(/ /g, "_");
		var service_handelr = service_name + "_settings";
		service_handelr = new frappe.integration_service[service_handelr]();
		service_handelr.get_service_info(frm);
		
		var scheduler_job_info = service_handelr.get_scheduler_job_info();
		frm.events.render_scheduler_jobs(frm, scheduler_job_info);
		
	},
	
	render_scheduler_jobs: function(frm, scheduler_job_info) {
		var schduler_job_view = frm.fields_dict.scheduler_events_html.wrapper;

		$(schduler_job_view).empty();
		$(schduler_job_view).append('\
			<table class="table table-bordered">\
				<thead>\
					<tr>\
						<th class="text-muted"> Event </th>\
						<th class="text-muted">  Action  </th>\
					</tr>\
				</thead> \
				<tbody></tbody> \
			</table>')

		$.each(scheduler_job_info, function(evnt, help){
			$row = $("<tr>").appendTo($(schduler_job_view).find("tbody"));
			$("<td>").appendTo($row).html(evnt).css("font-size", "12px");
			$("<td>").appendTo($row).html(help).css("font-size", "12px");
		})
	}
});
