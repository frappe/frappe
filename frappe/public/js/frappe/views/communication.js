// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.last_edited_communication = {};
frappe.standard_replies = {};

frappe.views.CommunicationComposer = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("Add Reply") + ": " + (this.subject || ""),
			no_submit_on_enter: true,
			fields: [
				{label:__("To"), fieldtype:"Data", reqd: 1, fieldname:"recipients"},

				{fieldtype: "Section Break"},
				{fieldtype: "Column Break"},
				{label:__("Subject"), fieldtype:"Data", reqd: 1,
					fieldname:"subject"},
				{fieldtype: "Column Break"},
				{label:__("Standard Reply"), fieldtype:"Link", options:"Standard Reply",
					fieldname:"standard_reply"},

				{fieldtype: "Section Break"},
				{label:__("Message"), fieldtype:"Text Editor", reqd: 1,
					fieldname:"content"},

				{fieldtype: "Section Break"},
				{fieldtype: "Column Break"},
				{label:__("Send As Email"), fieldtype:"Check",
					fieldname:"send_email"},
				{label:__("Send me a copy"), fieldtype:"Check",
					fieldname:"send_me_a_copy"},
				{label:__("Communication Medium"), fieldtype:"Select",
					options: ["Phone", "Chat", "Email", "SMS", "Visit", "Other"],
					fieldname:"communication_medium"},
				{label:__("Sent or Received"), fieldtype:"Select",
					options: ["Received", "Sent"],
					fieldname:"sent_or_received"},
				{label:__("Attach Document Print"), fieldtype:"Check",
					fieldname:"attach_document_print"},
				{label:__("Select Print Format"), fieldtype:"Select",
					fieldname:"select_print_format"},
				{fieldtype: "Column Break"},
				{label:__("Select Attachments"), fieldtype:"HTML",
					fieldname:"select_attachments"}
			],
			primary_action_label: "Send",
			primary_action: function() {
				me.send_action();
			}
		});

		$(document).on("upload_complete", function(event, attachment) {
			if(me.dialog.display) {
				var wrapper = $(me.dialog.fields_dict.select_attachments.wrapper);

				// find already checked items
				var checked_items = wrapper.find('[data-file-name]:checked').map(function() {
					return $(this).attr("data-file-name");
				});

				// reset attachment list
				me.setup_attach();

				// check latest added
				checked_items.push(attachment.file_name);

				$.each(checked_items, function(i, filename) {
					wrapper.find('[data-file-name="'+ filename +'"]').prop("checked", true);
				});
			}
		})
		this.prepare();
		this.dialog.show();

	},
	prepare: function() {
		this.setup_subject_and_recipients();
		this.setup_print();
		this.setup_attach();
		this.setup_email();
		this.setup_autosuggest();
		this.setup_last_edited_communication();
		this.setup_standard_reply();
		$(this.dialog.fields_dict.recipients.input).val(this.recipients || "").change();
		$(this.dialog.fields_dict.subject.input).val(this.subject || "").change();
		this.setup_earlier_reply();
	},

	setup_subject_and_recipients: function() {
		this.subject = this.subject || "";

		if(this.last_email) {
			this.recipients = this.last_email.comment_by;
		}

		if(!this.recipients) {
			this.recipients = this.frm && this.frm.comments.get_recipient();
		}

		if(!this.subject && this.frm) {
			// get subject from last communication
			var last = this.frm.comments.get_last_email();

			if(last) {
				this.subject = last.subject;
				if(!this.recipients) {
					this.recipients = last.comment_by;
				}

				// prepend "Re:"
				if(strip(this.subject.toLowerCase().split(":")[0])!="re") {
					this.subject = "Re: " + this.subject;
				}
			}

			if (!this.subject) {
				this.subject = __(this.frm.doctype) + ': ' + this.frm.docname;
			}
		}
	},

	setup_standard_reply: function() {
		var me = this;
		this.dialog.get_input("standard_reply").on("change", function() {
			var standard_reply = $(this).val();
			var prepend_reply = function() {
				var content_field = me.dialog.fields_dict.content;
				var content = content_field.get_value() || "";
				content_field.set_input(
					frappe.standard_replies[standard_reply]
						+ "<br><br>" + content);
			}
			if(frappe.standard_replies[standard_reply]) {
				prepend_reply();
			} else {
				$.ajax({
					url:"/api/resource/Standard Reply/" + standard_reply,
					statusCode: {
						200: function(data) {
							frappe.standard_replies[standard_reply] = data.data.response;
							prepend_reply();
						}
					}
				});
			}
		});
	},

	setup_last_edited_communication: function() {
		var me = this;
		this.dialog.onhide = function() {
			if(cur_frm && cur_frm.docname) {
				var last_edited_communication = me.get_last_edited_communication();
				$.extend(last_edited_communication, {
					recipients: me.dialog.get_value("recipients"),
					subject: me.dialog.get_value("subject"),
					content: me.dialog.get_value("content"),
				});
			}
		}

		this.dialog.on_page_show = function() {
			if (cur_frm && cur_frm.docname && !me.txt) {
				var last_edited_communication = me.get_last_edited_communication();
				if(last_edited_communication.content) {
					me.dialog.set_value("subject", last_edited_communication.subject || "");
					me.dialog.set_value("recipients", last_edited_communication.recipients || "");
					me.dialog.set_value("content", last_edited_communication.content || "");
				}
			}
		}

	},

	get_last_edited_communication: function() {
		var key = cur_frm.docname;
		if(this.last_email) {
			key = key + ":" + this.last_email.name;
		}
		if (!frappe.last_edited_communication[cur_frm.doctype]) {
			frappe.last_edited_communication[cur_frm.doctype] = {};
		}

		if(!frappe.last_edited_communication[cur_frm.doctype][key]) {
			frappe.last_edited_communication[cur_frm.doctype][key] = {};
		}

		return frappe.last_edited_communication[cur_frm.doctype][key];
	},

	setup_print: function() {
		// print formats
		var fields = this.dialog.fields_dict;

		// toggle print format
		$(fields.attach_document_print.input).click(function() {
			$(fields.select_print_format.wrapper).toggle($(this).prop("checked"));
		});

		// select print format
		$(fields.select_print_format.wrapper).toggle(false);

		if (cur_frm) {
			$(fields.select_print_format.input)
				.empty()
				.add_options(cur_frm.print_preview.print_formats)
				.val(cur_frm.print_preview.print_formats[0]);
		} else {
			$(fields.attach_document_print.wrapper).toggle(false);
		}

	},
	setup_attach: function() {
		if (!cur_frm) return;

		var fields = this.dialog.fields_dict;
		var attach = $(fields.select_attachments.wrapper);

		var files = cur_frm.get_files();
		if(files.length) {
			$("<h6 class='text-muted' style='margin-top: 12px;'>"
				+__("Add Attachments")+"</h6>").appendTo(attach.empty());
			$.each(files, function(i, f) {
				if (!f.file_name) return;
				f.file_url = frappe.urllib.get_full_url(f.file_url);

				$(repl('<p class="checkbox">'
					+	'<label><span><input type="checkbox" data-file-name="%(name)s"></input></span>'
					+		'<span class="small">%(file_name)s</span>'
					+	' <a href="%(file_url)s" target="_blank" class="text-muted small">'
					+		'<i class="icon-share" style="vertical-align: middle; margin-left: 3px;"></i>'
					+ '</label></p>', f))
					.appendTo(attach)
			});
		}
	},
	setup_email: function() {
		// email
		var me = this;
		var fields = this.dialog.fields_dict;

		if(this.attach_document_print) {
			$(fields.attach_document_print.input).click();
			$(fields.select_print_format.wrapper).toggle(true);
		}

		$(fields.send_email.input).prop("checked", true)

		// toggle print format
		$(fields.send_email.input).click(function() {
			$(fields.communication_medium.wrapper).toggle(!!!$(this).prop("checked"));
			$(fields.sent_or_received.wrapper).toggle(!!!$(this).prop("checked"));
			me.dialog.get_primary_btn().html($(this).prop("checked") ? "Send" : "Add Communication");
		});

		// select print format
		$(fields.communication_medium.wrapper).toggle(false);
		$(fields.sent_or_received.wrapper).toggle(false);

	},

	send_action: function() {
		var me = this,
			form_values = me.dialog.get_values(),
			btn = me.dialog.get_primary_btn();

		if(!form_values) return;

		var selected_attachments = $.map($(me.dialog.wrapper)
			.find("[data-file-name]:checked"), function(element) {
				return $(element).attr("data-file-name");
			})

		if(form_values.attach_document_print) {
			if (cur_frm.print_preview.is_old_style(form_values.select_print_format || "")) {
				cur_frm.print_preview.with_old_style({
					format: form_values.select_print_format,
					callback: function(print_html) {
						me.send_email(btn, form_values, selected_attachments, print_html);
					}
				});
			} else {
				me.send_email(btn, form_values, selected_attachments, null, form_values.select_print_format || "");
			}

		} else {
			me.send_email(btn, form_values, selected_attachments);
		}
	},

	send_email: function(btn, form_values, selected_attachments, print_html, print_format) {
		var me = this;

		if(!form_values.attach_document_print) {
			print_html = null;
			print_format = null;
		}

		if(form_values.send_email) {
			if(cur_frm && !frappe.model.can_email(me.doc.doctype, cur_frm)) {
				msgprint(__("You are not allowed to send emails related to this document"));
				return;
			}

			form_values.communication_medium = "Email";
			form_values.sent_or_received = "Sent";
		};

		return frappe.call({
			method:"frappe.core.doctype.communication.communication.make",
			args: {
				recipients: form_values.recipients,
				subject: form_values.subject,
				content: form_values.content,
				doctype: me.doc.doctype,
				name: me.doc.name,
				send_email: form_values.send_email,
				print_html: print_html,
				send_me_a_copy: form_values.send_me_a_copy,
				print_format: print_format,
				communication_medium: form_values.communication_medium,
				sent_or_received: form_values.sent_or_received,
				attachments: selected_attachments
			},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					if(form_values.send_email && r.message["recipients"])
						msgprint(__("Email sent to {0}", [r.message["recipients"]]));
					me.dialog.hide();

					if (cur_frm) {
						if (cur_frm.docname && (frappe.last_edited_communication[cur_frm.doctype] || {})[cur_frm.docname]) {
							delete frappe.last_edited_communication[cur_frm.doctype][cur_frm.docname];
						}
						// clear input
						cur_frm.comments.input.val("");
						cur_frm.reload_doc();
					}
				} else {
					msgprint(__("There were errors while sending email. Please try again."));
				}
			}
		});
	},

	setup_earlier_reply: function() {
		var fields = this.dialog.fields_dict,
			signature = frappe.boot.user.email_signature || "",
			last_email = this.last_email;

		if(!last_email) {
			last_email = this.frm && this.frm.comments.get_last_email(true);
		}

		if(!frappe.utils.is_html(signature)) {
			signature = signature.replace(/\n/g, "<br>");
		}

		if(this.txt) {
			this.message = this.txt + (this.message ? ("<br><br>" + this.message) : "");
		}

		if(this.real_name) {
			this.message = '<p>'+__('Dear') +' '
				+ this.real_name + ",</p>" + (this.message || "");
		}

		var reply = (this.message || "")
			+ (signature ? ("<br>" + signature) : "");

		if(last_email) {
			var last_email_content = last_email.original_comment || last_email.comment;

			fields.content.set_input(reply
				+ "<br><!-- original-reply --><br>"
				+ '<blockquote>' +
					'<p>' + __("On {0}, {1} wrote:",
					[frappe.datetime.global_date_format(last_email.creation) , last_email.comment_by]) + '</p>' +
					last_email_content +
				'<blockquote>');
		} else {
			fields.content.set_input(reply);
		}
	},
	setup_autosuggest: function() {
		var me = this;

		function split( val ) {
			return val.split( /,\s*/ );
		}
		function extractLast( term ) {
			return split(term).pop();
		}

		$(this.dialog.fields_dict.recipients.input)
			.bind( "keydown", function(event) {
				if (event.keyCode === $.ui.keyCode.TAB &&
						$(this).data( "autocomplete" ) &&
						$(this).data( "autocomplete" ).menu.active ) {
					event.preventDefault();
				}
			})
			.autocomplete({
				source: function(request, response) {
					return frappe.call({
						method:'frappe.email.get_contact_list',
						args: {
							'select': "email_id",
							'from': "Contact",
							'where': "email_id",
							'txt': extractLast(request.term).value || '%'
						},
						quiet: true,
						callback: function(r) {
							response($.ui.autocomplete.filter(
								r.cl || [], extractLast(request.term)));
						}
					});
				},
				appendTo: this.dialog.$wrapper,
				focus: function() {
					// prevent value inserted on focus
					return false;
				},
				select: function( event, ui ) {
					var terms = split( this.value );
					// remove the current input
					terms.pop();
					// add the selected item
					terms.push( ui.item.value );
					// add placeholder to get the comma-and-space at the end
					terms.push( "" );
					this.value = terms.join( ", " );
					return false;
				}
			});
	}
});

