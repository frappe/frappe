// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

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
			frm.events.load_js_resouce(frm);
		}
	},

	load_js_resouce: function(frm){
		frappe.call({
			method: 'frappe.integration_broker.doctype.integration_service.integration_service.get_js_resouce',
			args: {
				'service': frm.doc.service
			},
			callback: function(r) {
				$(frm.fields_dict.custom_settings.wrapper).empty();

				if (r.message.js){
					frm.clear_custom_buttons();
					frappe.require(r.message.js, function(){
						service_name = frm.doc.service.toLowerCase().replace(/ /g, "_");
						frappe.integration_service[service_name].load(frm);

						$(frm.fields_dict.scheduler_events_html.wrapper).empty();

						if (frappe.integration_service[service_name].scheduler_job_helper) {
							frm.scheduler_helper = frappe.integration_service[service_name].scheduler_job_helper();
							frm.events.render_scheduler_jobs(frm);
						}
					})
				}

				frm.events.load_parameters(frm);
			}
		})
	},
	
	load_parameters: function(frm) {
		var form = frm;

		frappe.call({
			method: 'frappe.integration_broker.doctype.integration_service.integration_service.get_service_parameters',
			args: {
				'service': frm.doc.service
			},
			callback: function(r) {
				frm.fields = r.message.parameters;
				frm.scheduler_jobs = r.message.scheduled_jobs;
				frm.events.show_properties(frm);
			}
		});
	},
	
	edit_settings: function(frm) {
		frm.events.setup_dialog(frm);
	},

	setup_dialog: function(frm){
		var d = new frappe.ui.Dialog({
			title:__('Custom Settings'),
			fields: frm.fields
		});

		// set_value
		if(frm.doc.custom_settings_json){
			d.set_values(JSON.parse(frm.doc.custom_settings_json));
		}

		d.set_primary_action(__("Set"), function() {
			var btn = this;
			var v = d.get_values();
			if(!v) return;

			frm.set_value("custom_settings_json", JSON.stringify(v));
			frm.refresh_field("custom_settings_json");
			d.hide();
			frm.events.show_properties(frm);
		})

		d.show();
	},

	show_properties:function(frm){
		var frm = frm;
		var table_wrapper = frm.fields_dict.custom_settings.wrapper;
		
		frm.settings = frm.doc.custom_settings_json ? JSON.parse(frm.doc.custom_settings_json) : {};
		
		$(table_wrapper).empty();
		$(table_wrapper).append('\
			<table class="table table-bordered" style="cursor: pointer;">\
				<thead>\
					<tr>\
						<th class="text-muted"> Parameter </th>\
						<th class="text-muted">  Value  </th>\
					</tr>\
				</thead> \
				<tbody></tbody> \
			</table>')

		frm.fields.forEach(function(d){
			var df = d;
			$row = $("<tr>").appendTo($(table_wrapper).find("tbody"));
			$("<td>").appendTo($row).html(__(d.label)).css("font-size", "12px");
			pwd_length = frm.settings[d.fieldname] ? frm.settings[d.fieldname].length : 0
			value = (d.fieldtype == "Password") ? "*".repeat(pwd_length) : frm.settings[d.fieldname];
			$("<td>").appendTo($row).html(value).css("font-size", "12px");
		});
		
		$(table_wrapper).find(".table-bordered").click(function(){
			frm.events.setup_dialog(frm);
		})
	},
	
	render_scheduler_jobs: function(frm) {
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
		
		$.each(frm.scheduler_helper, function(evnt, help){
			$row = $("<tr>").appendTo($(schduler_job_view).find("tbody"));
			$("<td>").appendTo($row).html(evnt).css("font-size", "12px");
			$("<td>").appendTo($row).html(help).css("font-size", "12px");
		})
	}
});
