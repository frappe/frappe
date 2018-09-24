// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("Event", {
	onload: function(frm) {
		frm.set_query('reference_doctype', "event_participants", function() {
			return {
				"filters": {
					"issingle": 0,
				}
			};
		})
	},
	refresh: function(frm) {
		if(frm.doc.event_participants) {
			frm.doc.event_participants.forEach(value => {
				frm.add_custom_button(__(value.reference_docname), function() {
					frappe.set_route("Form", value.reference_doctype, value.reference_docname);
				}, __("Participants"));
			})
		}
	},
	repeat_on: function(frm) {
		if(frm.doc.repeat_on==="Every Day") {
			["monday", "tuesday", "wednesday", "thursday",
				"friday", "saturday", "sunday"].map(function(v) {
					frm.set_value(v, 1);
				});
		}
	}
});

frappe.ui.form.on("Event Participants", {
	event_participants_remove: function(frm, cdt, cdn) {
		frappe.call({
			type: "POST",
			method: "frappe.desk.doctype.event.event.delete_communication",
			args: {
				"event": frm.doc,
				"reference_doctype": cdt,
				"reference_docname": cdn
			},
			freeze: true,
			callback: function(r) {
				if(r.exc) {
					frappe.show_alert({
						message: __("{0}", [r.exc]),
						indicator: 'orange'
					});
				}
			}
		});
	}
});

