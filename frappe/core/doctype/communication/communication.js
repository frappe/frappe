frappe.ui.form.on("Communication", {
	onload: function(frm) {
		if(frm.doc.content) {
			frm.doc.content = frappe.dom.remove_script_and_style(frm.doc.content);
		}
		frm.set_query("reference_doctype", function() {
			return {
				filters: {
					"issingle": 0,
					"istable": 0
				}
			}
		});
	},
	refresh: function(frm) {
		if(frm.is_new()) return;

		frm.convert_to_click && frm.set_convert_button();
		frm.subject_field = "subject";

		if(frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__(frm.doc.reference_name), function() {
				frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
			});
		} else {
			// if an unlinked communication, set email field
			if (frm.doc.sent_or_received==="Received") {
				frm.email_field = "sender";
			} else {
				frm.email_field = "recipients";
			}
		}

		if(frm.doc.communication_type == "Feedback") {
			frm.add_custom_button(__("Resend"), function() {
				var feedback = new frappe.utils.Feedback();
				feedback.resend_feedback_request(frm.doc);
			});
		}

		if(frm.doc.status==="Open") {
			frm.add_custom_button(__("Close"), function() {
				frm.set_value("status", "Closed");
				frm.save();
			});
		} else if (frm.doc.status !== "Linked") {
			frm.add_custom_button(__("Reopen"), function() {
				frm.set_value("status", "Open");
				frm.save();
			});
		}

		frm.add_custom_button(__("Relink"), function() {
			frm.trigger('show_relink_dialog');
		});

		if(frm.doc.communication_type=="Communication" 
			&& frm.doc.communication_medium == "Email"
			&& frm.doc.sent_or_received == "Received") {

			frm.add_custom_button(__("Reply"), function() {
				frm.trigger('reply');
			});

			frm.add_custom_button(__("Reply All"), function() {
				frm.trigger('reply_all');
			}, "Actions");

			frm.add_custom_button(__("Forward"), function() {
				frm.trigger('forward_mail');
			}, "Actions");

			frm.add_custom_button(__("Mark as {0}", [frm.doc.seen? "Unread": "Read"]), function() {
				frm.trigger('mark_as_read_unread');
			}, "Actions");

			frm.add_custom_button(__("Add Contact"), function() {
				frm.trigger('add_to_contact');
			}, "Actions");

			if(frm.doc.email_status != "Spam")
				frm.add_custom_button(__("Mark as Spam"), function() {
					frm.trigger('mark_as_spam');
				}, "Actions");

			if(frm.doc.email_status != "Trash") {
				frm.add_custom_button(__("Move To Trash"), function() {
					frm.trigger('move_to_trash');
				}, "Actions");
			}
		}
	},
	show_relink_dialog: function(frm){
		var lib = "frappe.email";
		var d = new frappe.ui.Dialog ({
			title: __("Relink Communication"),
			fields: [{
				"fieldtype": "Link",
				"options": "DocType",
				"label": __("Reference Doctype"),
				"fieldname": "reference_doctype",
				"get_query": function() {return {"query": "frappe.email.get_communication_doctype"}}
			},
			{
				"fieldtype": "Dynamic Link",
				"options": "reference_doctype",
				"label": __("Reference Name"),
				"fieldname": "reference_name"
			}]
		});
		d.set_value("reference_doctype", frm.doc.reference_doctype);
		d.set_value("reference_name", frm.doc.reference_name);
		d.set_primary_action(__("Relink"), function () {
			var values = d.get_values();
			if (values) {
				frappe.confirm(
					__('Are you sure you want to relink this communication to {0}?', [values["reference_name"]]),
					function () {
						d.hide();
						frappe.call({
							method: "frappe.email.relink",
							args: {
								"name": frm.doc.name,
								"reference_doctype": values["reference_doctype"],
								"reference_name": values["reference_name"]
							},
							callback: function () {
								frm.refresh();
							}
						});
					},
					function () {
						frappe.show_alert('Document not Relinked')
					}
				);
			}
		});
		d.show();
	},

	mark_as_read_unread: function(frm) {
		var action = frm.doc.seen? "Unread": "Read";
		var flag = "(\\SEEN)";

		return frappe.call({
			method: "frappe.email.inbox.create_email_flag_queue",
			args: {
				'names': [frm.doc.name],
				'action': action,
				'flag': flag
			},
			freeze: true
		});
	},

	reply: function(frm) {
		var args = frm.events.get_mail_args(frm);
		$.extend(args, {
			subject: __("Re: {0}", [frm.doc.subject]),
			recipients: frm.doc.sender
		})

		new frappe.views.CommunicationComposer(args);
	},

	reply_all: function(frm) {
		var args = frm.events.get_mail_args(frm)
		$.extend(args, {
			subject: __("Re: {0}", [frm.doc.subject]),
			recipients: frm.doc.sender,
			cc: frm.doc.cc
		})
		new frappe.views.CommunicationComposer(args);
	},

	forward_mail: function(frm) {
		var args = frm.events.get_mail_args(frm)
		$.extend(args, {		
			forward: true,
			subject: __("Fw: {0}", [frm.doc.subject]),
		})

		new frappe.views.CommunicationComposer(args);
	},

	get_mail_args: function(frm) {
		var sender_email_id = ""
		$.each(frappe.boot.email_accounts, function(idx, account) {
			if(account.email_account == frm.doc.email_account) {
				sender_email_id = account.email_id
				return
			}
		});

		return {
			frm: frm,
			doc: frm.doc,
			last_email: frm.doc,
			sender: sender_email_id,
			attachments: frm.doc.attachments
		}
	},

	add_to_contact: function(frm) {
		var me = this;
		var fullname = frm.doc.sender_full_name || ""

		var names = fullname.split(" ")
		var first_name = names[0]
		var last_name = names.length >= 2? names[names.length - 1]: ""

		frappe.route_options = {
			"email_id": frm.doc.sender,
			"first_name": first_name,
			"last_name": last_name,
		}
		frappe.new_doc("Contact")
	},

	mark_as_spam: function(frm) {
		frappe.call({
			method: "frappe.email.inbox.mark_as_spam",
			args: {
				communication: frm.doc.name,
				sender: frm.doc.sender
			},
			freeze: true,
			callback: function(r) {
				frappe.msgprint(__("Email has been marked as spam"))
			}
		})
	},

	move_to_trash: function(frm) {
		frappe.call({
			method: "frappe.email.inbox.mark_as_trash",
			args: {
				communication: frm.doc.name
			},
			freeze: true,
			callback: function(r) {
				frappe.msgprint(__("Email has been moved to trash"))
			}
		})
	}
});
