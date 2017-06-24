frappe.provide("frappe.utils")

frappe.utils.Feedback = Class.extend({
	resend_feedback_request: function(doc) {
		/* resend the feedback request email */
		var args = {
			reference_name: doc.reference_name,
			reference_doctype: doc.reference_doctype,
			request: doc.feedback_request,
		}
		this.get_feedback_request_details(args, true)
	},

	manual_feedback_request: function(doc) {
		var me = this;

		var args = {
			reference_doctype: doc.doctype,
			reference_name: doc.name
		}
		if(frappe.boot.feedback_triggers[doc.doctype]) {
			var feedback_trigger = frappe.boot.feedback_triggers[doc.doctype]
			$.extend(args, { trigger: feedback_trigger })
			me.get_feedback_request_details(args, false)
		} else{
			me.make_feedback_request_dialog(args, false)
		}
	},

	get_feedback_request_details: function(args, is_resend) {
		var me = this;

		return frappe.call({
			method: "frappe.core.doctype.feedback_trigger.feedback_trigger.get_feedback_request_details",
			'args': args,
			callback: function(r) {
				if(r.message) {
					me.make_feedback_request_dialog(r.message, is_resend)
				}
			}
		});
	},

	make_feedback_request_dialog: function(args, is_resend) {
		var me = this;
		var dialog = new frappe.ui.Dialog({
			title: __("{0} Feedback Request", [ is_resend? "Resend": "Send" ]),
			fields: [
				{
					"reqd": 1,
					"label": __("Recipient"), 
					"fieldname": "recipients",
					"fieldtype": "Data",
					"options": "Email"
				},
				{
					"reqd": 1,
					"label": __("Subject"), 
					"fieldname": "subject",
					"fieldtype": "Data"
				},
				{
					"reqd": 1,
					"label": __("Message"), 
					"fieldname": "message",
					"fieldtype": "Text Editor"
				}
			],
		});

		$.each(args, function(field, value){
			dialog.set_value(field, value);
		})

		dialog.set_primary_action(__("Send"), function() {
			$.extend(args,{ details: dialog.get_values() });
			if(!args)
				return;

			dialog.hide();
			me.send_feedback_request(args)
		});

		dialog.show();
	},

	send_feedback_request: function(args) {
		$.extend(args, { is_manual: true })
		return frappe.call({
			method: "frappe.core.doctype.feedback_trigger.feedback_trigger.send_feedback_request",
			'args': args,
			freeze: true,
			callback: function(r) {
				if(r.message) {
					frappe.msgprint(__("Feedback Request for {0} is sent to {1}",
						[args.reference_name, args.details.recipients]));
				}
			}
		});
	}
})

