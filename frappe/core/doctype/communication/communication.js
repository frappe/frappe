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

		if(frm.doc.dynamic_links) {
			for (var link in frm.doc.dynamic_links) {
				let dynamic_link = frm.doc.dynamic_links[link];
				frm.add_custom_button(__(dynamic_link.link_doctype) + ": " + dynamic_link.link_name, function () {
					frappe.set_route("Form", dynamic_link.link_doctype, dynamic_link.link_name);
				}, __("View"));
			}
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

		frm.add_custom_button(__("Add link"), function() {
			frm.trigger('show_add_link_dialog');
		});

		frm.add_custom_button(__("Remove link"), function() {
			frm.trigger('show_remove_link_dialog');
		});

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

		if(frm.doc.communication_type=="Communication"
			&& frm.doc.communication_medium == "Phone"
			&& frm.doc.sent_or_received == "Received"){

			frm.add_custom_button(__("Add Contact"), function() {
				frm.trigger('add_to_contact');
			}, "Actions");
		}
	},

	show_add_link_dialog: function(frm){
		var d = new frappe.ui.Dialog ({
			title: __("Add new link to Communication"),
			fields: [{
				"fieldtype": "Link",
				"options": "DocType",
				"label": __("Document Type"),
				"fieldname": "link_doctype",
				"reqd": 1
			},
			{
				"fieldtype": "Dynamic Link",
				"options": "link_doctype",
				"label": __("Document Name"),
				"fieldname": "link_name",
				"reqd": 1
			}],
			primary_action: ({ link_doctype, link_name }) => {
				d.hide();
				frm.call('add_link', {
					link_doctype,
					link_name,
					autosave: true
				}).then(() => frm.refresh());
			},
			primary_action_label: __('Add Link')
		});
		d.fields_dict.link_doctype.get_query = function() {
			return {
				"filters": {
					"name": ["!=", "Communication"],
				}
			};
		};
		d.show();
	},

	show_remove_link_dialog: function(frm){
		let options = '';

		for(var link in frm.doc.dynamic_links){
			let dynamic_link = frm.doc.dynamic_links[link];
			options += '\n' + dynamic_link.link_doctype + ': ' + dynamic_link.link_name;
		}

		var d = new frappe.ui.Dialog ({
			title: __("Remove link from Communication"),
			fields: [{
				"fieldtype": "Select",
				"options": options,
				"label": __("Link"),
				"fieldname": "link",
				"reqd": 1
			}],
			primary_action: ({ link }) => {
				d.hide();
				frm.call('remove_link', {
					link_doctype: link.split(":")[0].trim(),
					link_name: link.split(":")[1].trim(),
					autosave: true
				}).then(() => frm.refresh());
			},
			primary_action_label: __('Remove Link')
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
			subject: __("Res: {0}", [frm.doc.subject]),
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
			"email_id": frm.doc.sender || "",
			"first_name": first_name,
			"last_name": last_name,
			"mobile_no": frm.doc.phone_no || ""
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