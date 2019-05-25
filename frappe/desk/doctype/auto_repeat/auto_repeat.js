// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt
frappe.provide("frappe.auto_repeat");

frappe.ui.form.on('Auto Repeat', {
	setup: function(frm) {
		frm.fields_dict['reference_doctype'].get_query = function() {
			return {
				query: "frappe.desk.doctype.auto_repeat.auto_repeat.auto_repeat_doctype_query"
			};
		};

		frm.fields_dict['reference_document'].get_query = function() {
			return {
				filters: {
					"docstatus": 1,
					"auto_repeat": ''
				}
			};
		};

		frm.fields_dict['print_format'].get_query = function() {
			return {
				filters: {
					"doc_type": frm.doc.reference_doctype
				}
			};
		};
	},

	refresh: function(frm) {

		if(frm.doc.docstatus == 1) {

			let label = __('View {0}', [__(frm.doc.reference_doctype)]);
			frm.add_custom_button(__(label),
				function() {
					frappe.route_options = {
						"auto_repeat": frm.doc.name,
					};
					frappe.set_route("List", frm.doc.reference_doctype);
				}
			);

			if(frm.doc.status != 'Stopped') {
				frm.add_custom_button(__("Stop"),
					function() {
						frm.events.stop_resume_auto_repeat(frm, "Stopped");
					}
				);
			}

			if(frm.doc.status == 'Stopped') {
				frm.add_custom_button(__("Restart"),
					function() {
						frm.events.stop_resume_auto_repeat(frm, "Resumed");
					}
				);
			}
		}

		frm.toggle_display('auto_repeat_schedule', !in_list(['Stopped', 'Cancelled'], frm.doc.status));
		if(frm.doc.start_date && !in_list(['Stopped', 'Cancelled'], frm.doc.status)){
			frappe.auto_repeat.render_schedule(frm);
		}

	},

	stop_resume_auto_repeat: function(frm, status) {
		frappe.call({
			method: "frappe.desk.doctype.auto_repeat.auto_repeat.stop_resume_auto_repeat",
			args: {
				auto_repeat: frm.doc.name,
				status: status
			},
			callback: function(r) {
				if(r.message) {
					frm.set_value("status", r.message);
					frm.reload_doc();
				}
			}
		});
	},

	template: function(frm) {
		if (frm.doc.template) {
			frappe.model.with_doc("Email Template", frm.doc.template, () => {
				let email_template = frappe.get_doc("Email Template", frm.doc.template);
				frm.set_value("subject", email_template.subject);
				frm.set_value("message", email_template.response);
				frm.refresh_field("subject");
				frm.refresh_field("message");
			});
		}
	},

	get_contacts: function(frm) {
		frappe.call({
			method: "frappe.desk.doctype.auto_repeat.auto_repeat.get_contacts",
			args: {
				reference_doctype: frm.doc.reference_doctype,
				reference_name: frm.doc.reference_document
			},
			callback: function(r) {
				if(r.message) {
					frm.set_value("recipients", r.message.join());
					frm.refresh_field("recipients");
				}
			}
		});
	},

	preview_message: function(frm) {
		if (frm.doc.message) {
			frappe.call({
				method: "frappe.desk.doctype.auto_repeat.auto_repeat.generate_message_preview",
				args: {
					reference_dt: frm.doc.reference_doctype,
					reference_doc: frm.doc.reference_document,
					subject: frm.doc.subject,
					message: frm.doc.message
				},
				callback: function(r) {
					if(r.message) {
						frappe.msgprint(r.message.message, r.message.subject)
					}
				}
			});
		} else {
			frappe.msgprint(__("Please setup a message first"), __("Message not setup"))
		}
	}
});

frappe.auto_repeat.render_schedule = function(frm) {
	frappe.call({
		method: "get_auto_repeat_schedule",
		doc: frm.doc
	}).done((r) => {
		var wrapper = $(frm.fields_dict["auto_repeat_schedule"].wrapper);
		wrapper.html(frappe.render_template ("auto_repeat_schedule", {"schedule_details" : r.message || []}  ));
		frm.refresh_fields();
	});
};