// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("desk");

frappe.ui.form.on("Event", {
	refresh: function(frm) {
		if(frm.doc.ref_type && frm.doc.ref_name) {
			frm.add_custom_button(__(frm.doc.ref_name), function() {
				frappe.set_route("Form", frm.doc.ref_type, frm.doc.ref_name);
			});
		}

		frm.set_query('reference_doctype', "event_participants", function() {
			return {
				"filters": {
					"name": ["in", ["Contact", "Lead", "Customer", "Supplier", "Employee"]]
				}
			};
		})

		add_custom_btns(frm);
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

let add_custom_btns = (frm) => {
	frm.page.set_inner_btn_group_as_primary(__("Add Participants"));

	frm.add_custom_button(__('Add Contacts'), function() {
		new desk.eventParticipants(frm, "Contact");
	}, __("Add Participants"));

	frm.add_custom_button(__('Add Leads'), function() {
		new desk.eventParticipants(frm, "Lead");
	}, __("Add Participants"));

	frm.add_custom_button(__('Add Customers'), function() {
		new desk.eventParticipants(frm, "Customer");
	}, __("Add Participants"));

	frm.add_custom_button(__('Add Suppliers'), function() {
		new desk.eventParticipants(frm, "Supplier");
	}, __("Add Participants"));

	frm.add_custom_button(__('Add Employees'), function() {
		new desk.eventParticipants(frm, "Employee");
	}, __("Add Participants"));
}

desk.eventParticipants = class eventParticipants {
	constructor(frm, doctype) {
		this.frm = frm;
		this.doctype = doctype;
		this.make();
	}

	make() {
		let me = this;

		let table = me.frm.get_field("event_participants").grid;
		new frappe.ui.form.LinkSelector({
			doctype: me.doctype,
			dynamic_link_field: "reference_doctype",
			dynamic_link_reference: me.doctype,
			fieldname: "reference_docname",
			target: table,
			txt: ""
		});
	}
};


