frappe.ui.form.on("Communication", {
	onload: function (frm) {
		if (frm.doc.content) {
			frm.doc.content = frappe.dom.remove_script_and_style(frm.doc.content);
		}
		frm.set_query("reference_doctype", function () {
			return {
				filters: {
					issingle: 0,
					istable: 0,
				},
			};
		});
	},
	refresh: function (frm) {
		if (frm.is_new()) return;

		frm.convert_to_click && frm.set_convert_button();
		frm.subject_field = "subject";

		// content field contains weird table html that does not render well in Quill
		// this field is not to be edited directly anyway, so setting it as read only
		frm.set_df_property("content", "read_only", 1);

		if (frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__(frm.doc.reference_name), function () {
				frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
			});
		} else {
			// if an unlinked communication, set email field
			if (frm.doc.sent_or_received === "Received") {
				frm.email_field = "sender";
			} else {
				frm.email_field = "recipients";
			}
		}

		if (frm.doc.status === "Open") {
			frm.add_custom_button(__("Close"), function () {
				frm.trigger("mark_as_closed_open");
			});
		} else if (frm.doc.status !== "Linked") {
			frm.add_custom_button(__("Reopen"), function () {
				frm.trigger("mark_as_closed_open");
			});
		}

		frm.add_custom_button(__("Relink"), function () {
			frm.trigger("show_relink_dialog");
		});

		if (
			frm.doc.communication_type == "Communication" &&
			frm.doc.communication_medium == "Email" &&
			frm.doc.sent_or_received == "Received"
		) {
			frm.add_custom_button(__("Reply"), function () {
				frm.trigger("reply");
			});

			frm.add_custom_button(
				__("Reply All"),
				function () {
					frm.trigger("reply_all");
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Forward"),
				function () {
					frm.trigger("forward_mail");
				},
				__("Actions")
			);

			frm.add_custom_button(
				frm.doc.seen ? __("Mark as Unread") : __("Mark as Read"),
				function () {
					frm.trigger("mark_as_read_unread");
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Move"),
				function () {
					frm.trigger("show_move_dialog");
				},
				__("Actions")
			);

			if (frm.doc.email_status != "Spam")
				frm.add_custom_button(
					__("Mark as Spam"),
					function () {
						frm.trigger("mark_as_spam");
					},
					__("Actions")
				);

			if (frm.doc.email_status != "Trash") {
				frm.add_custom_button(
					__("Move To Trash"),
					function () {
						frm.trigger("move_to_trash");
					},
					__("Actions")
				);
			}

			frm.add_custom_button(
				__("Contact"),
				function () {
					frm.trigger("add_to_contact");
				},
				__("Create")
			);
		}

		if (
			frm.doc.communication_type == "Communication" &&
			frm.doc.communication_medium == "Phone" &&
			frm.doc.sent_or_received == "Received"
		) {
			frm.add_custom_button(
				__("Add Contact"),
				function () {
					frm.trigger("add_to_contact");
				},
				__("Actions")
			);
		}
	},

	show_relink_dialog: function (frm) {
		var d = new frappe.ui.Dialog({
			title: __("Relink Communication"),
			fields: [
				{
					fieldtype: "Link",
					options: "DocType",
					label: __("Reference Doctype"),
					fieldname: "reference_doctype",
					get_query: function () {
						return { query: "frappe.email.get_communication_doctype" };
					},
				},
				{
					fieldtype: "Dynamic Link",
					options: "reference_doctype",
					label: __("Reference Name"),
					fieldname: "reference_name",
				},
			],
		});
		d.set_value("reference_doctype", frm.doc.reference_doctype);
		d.set_value("reference_name", frm.doc.reference_name);
		d.set_primary_action(__("Relink"), function () {
			var values = d.get_values();
			if (values) {
				frappe.confirm(
					__("Are you sure you want to relink this communication to {0}?", [
						values["reference_name"],
					]),
					function () {
						d.hide();
						frappe.call({
							method: "frappe.email.relink",
							args: {
								name: frm.doc.name,
								reference_doctype: values["reference_doctype"],
								reference_name: values["reference_name"],
							},
							callback: function () {
								frm.refresh();
							},
						});
					},
					function () {
						frappe.show_alert({
							message: __("Document not Relinked"),
							indicator: "info",
						});
					}
				);
			}
		});
		d.show();
	},

	show_move_dialog: function (frm) {
		var d = new frappe.ui.Dialog({
			title: __("Move"),
			fields: [
				{
					fieldtype: "Link",
					options: "Email Account",
					label: __("Email Account"),
					fieldname: "email_account",
					reqd: 1,
					get_query: function () {
						return {
							filters: {
								name: ["!=", frm.doc.email_account],
								enable_incoming: ["=", 1],
							},
						};
					},
				},
			],
			primary_action_label: __("Move"),
			primary_action(values) {
				d.hide();
				frappe.call({
					method: "frappe.email.inbox.move_email",
					args: {
						communication: frm.doc.name,
						email_account: values.email_account,
					},
					freeze: true,
					callback: function () {
						window.history.back();
					},
				});
			},
		});
		d.show();
	},

	mark_as_read_unread: function (frm) {
		var action = frm.doc.seen ? "Unread" : "Read";
		var flag = "(\\SEEN)";

		return frappe.call({
			method: "frappe.email.inbox.create_email_flag_queue",
			args: {
				names: [frm.doc.name],
				action: action,
				flag: flag,
			},
			freeze: true,
			callback: function () {
				frm.reload_doc();
			},
		});
	},

	mark_as_closed_open: function (frm) {
		var status = frm.doc.status == "Open" ? "Closed" : "Open";

		return frappe.call({
			method: "frappe.email.inbox.mark_as_closed_open",
			args: {
				communication: frm.doc.name,
				status: status,
			},
			freeze: true,
			callback: function () {
				frm.reload_doc();
			},
		});
	},

	reply: function (frm) {
		var args = frm.events.get_mail_args(frm);
		$.extend(args, {
			subject: __("Re: {0}", [frm.doc.subject]),
			recipients: frm.doc.sender,
		});

		new frappe.views.CommunicationComposer(args);
	},

	reply_all: function (frm) {
		var args = frm.events.get_mail_args(frm);
		$.extend(args, {
			subject: __("Res: {0}", [frm.doc.subject]),
			recipients: frm.doc.sender,
			cc: frm.doc.cc,
		});
		new frappe.views.CommunicationComposer(args);
	},

	forward_mail: function (frm) {
		var args = frm.events.get_mail_args(frm);
		$.extend(args, {
			forward: true,
			subject: __("Fw: {0}", [frm.doc.subject]),
		});

		new frappe.views.CommunicationComposer(args);
	},

	get_mail_args: function (frm) {
		var sender_email_id = "";
		$.each(frappe.boot.email_accounts, function (idx, account) {
			if (account.email_account == frm.doc.email_account) {
				sender_email_id = account.email_id;
				return;
			}
		});

		return {
			frm: frm,
			doc: frm.doc,
			last_email: frm.doc,
			sender: sender_email_id,
			attachments: frm.doc.attachments,
		};
	},

	add_to_contact: function (frm) {
		var me = this;
		var fullname = frm.doc.sender_full_name || "";

		var names = fullname.split(" ");
		var first_name = names[0];
		var last_name = names.length >= 2 ? names[names.length - 1] : "";

		frappe.route_options = {
			email_id: frm.doc.sender || "",
			first_name: first_name,
			last_name: last_name,
			mobile_no: frm.doc.phone_no || "",
		};
		frappe.new_doc("Contact");
	},

	mark_as_spam: function (frm) {
		frappe.call({
			method: "frappe.email.inbox.mark_as_spam",
			args: {
				communication: frm.doc.name,
				sender: frm.doc.sender,
			},
			freeze: true,
			callback: function (r) {
				frappe.msgprint(__("Email has been marked as spam"));
			},
		});
	},

	move_to_trash: function (frm) {
		frappe.call({
			method: "frappe.email.inbox.mark_as_trash",
			args: {
				communication: frm.doc.name,
			},
			freeze: true,
			callback: function (r) {
				frappe.msgprint(__("Email has been moved to trash"));
			},
		});
	},
});
