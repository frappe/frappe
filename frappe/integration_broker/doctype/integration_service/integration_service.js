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
	service: function(frm) {
		frappe.call({
			method: 'frappe.integration_broker.doctype.integration_service.integration_service.get_events_and_parameters',
			args: {
				'service': frm.doc.service
			},
			callback: function(r) {
				frm.clear_table('parameters');
				r.message.parameters.forEach(function(d) {
					frm.add_child('parameters', {'label': d.label, 'fieldname': d.fieldname, 'value': d.value})
				});

				frm.clear_table('events');
				r.message.events.forEach(function(d) {
					frm.add_child('events', {'event': d.event, 'enabled': d.enabled})
				});
				
				frm.refresh();
			}
		});
	},
	load_js_resouce: function(frm){
		frappe.call({
			method: 'frappe.integration_broker.doctype.integration_service.integration_service.get_js_resouce',
			args: {
				'service': frm.doc.service
			},
			callback: function(r) {
				if (r.message.js){
					frappe.require(r.message.js, function(){
						service_name = frm.doc.service.toLowerCase().replace(/ /g, "_");
						frappe.integration_service[service_name].load(frm)
					})
				}
			
			}
		})
	}
});
