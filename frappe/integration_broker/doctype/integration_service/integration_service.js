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
					if (!d.show_in_dialog) {
						frm.add_child('parameters', {'label': d.label, 'fieldname': d.fieldname, 'value': d.default})
					}
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
				$(frm.fields_dict.custom_settings.wrapper).empty();
				$(frm.fields_dict.custom_settings_display.wrapper).empty();

				if (r.message.js){
					frm.clear_custom_buttons();
					frappe.require(r.message.js, function(){
						service_name = frm.doc.service.toLowerCase().replace(/ /g, "_");
						frappe.integration_service[service_name].load(frm)
					})
				}
				frm.events.custom_settings(frm);
			}
		})
	},

	custom_settings: function(frm){
		var form = frm;
		var wrapper = frm.fields_dict.custom_settings.wrapper;

		$(wrapper).empty();
		$(wrapper).append("<a class='label-area small additional_settings'> Additional Settings </a>");

		frappe.call({
			method: "frappe.integration_broker.doctype.integration_service.integration_service.get_events_and_parameters",
			args: {
				'service': frm.doc.service
			},
			callback: function(r){
				frm.fields = [];

				r.message.parameters.forEach(function(d) {
					if (d.show_in_dialog) {
						frm.fields.push(d);
					}
				})

				$(wrapper).find(".additional_settings").click(function(){
					form.events.setup_dialog(form);
				});

				frm.events.show_additional_properties(frm)
			}
		});
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
			frm.events.show_additional_properties(frm);
		})

		d.show();
	},

	show_additional_properties:function(frm){
		var table_wrapper = frm.fields_dict.custom_settings_display.wrapper;
		frm.settings = JSON.parse(frm.doc.custom_settings_json);

		$(table_wrapper).empty();

		$(table_wrapper).append('\
			<table class="table table-bordered table-hover">\
				<thead>\
					<tr>\
						<th> Parameter </th>\
						<th> Value </th>\
					</tr>\
				</thead> \
				<tbody></tbody> \
			</table>')

		frm.fields.forEach(function(d){
			var df = d;
			$row = $("<tr>").appendTo($(table_wrapper).find("tbody"));
			$("<td>").appendTo($row).html(__(d.label));
			$("<td>").appendTo($row).html(frm.settings[d.fieldname]);
		})
	}
});
