// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Server Script', {
	refresh: function(frm) {
		if(frm.doc.script_type === 'Scheduler Event' && !frm.doc.disabled){
			frm.add_custom_button('Schedule Script', function() {
				var d = new frappe.ui.Dialog({
					title: "Schedule Script Execution",
					fields: [
						{
							fieldname: "event_type",
							label: __('Select Event Type'),
							fieldtype: "Select",
							options: "All\nHourly\nDaily\nWeekly\nMonthly\nYearly\nHourly Long\nDaily Long\nWeekly Long\nMonthly Long"
						},
					],
					primary_action_label: __('Schedule Script'),
					primary_action: () => {
						d.get_primary_btn().attr('disabled', true);
						var data = d.get_values();
						d.hide();
						if(data) {
							frm.events.schedule_script(frm, data);
						}

					}
				});

				d.show();

			});
		}
	},

	schedule_script(frm, data){
		frm.call({
			method: "frappe.core.doctype.server_script.server_script.setup_scheduler_events",
			args: {
				'script_name': frm.doc.name,
				'frequency': data.event_type
			}
		})
	}

});
