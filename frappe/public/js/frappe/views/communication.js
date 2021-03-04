// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.last_edited_communication = {};
frappe.standard_replies = {};
frappe.separator_element = '<div>---</div>';

frappe.views.CommunicationComposer = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;

		this.dialog = new frappe.ui.Dialog({
			title: (this.title || this.subject || __("New Email")),
			no_submit_on_enter: true,
			fields: this.get_fields(),
			primary_action_label: __("Send"),
			size: 'large',
			primary_action: function() {
				me.delete_saved_draft();
				me.send_action();
			},
			minimizable: true
		});

		this.dialog.sections[0].wrapper.addClass('to_section');

		['recipients', 'cc', 'bcc'].forEach(field => {
			this.dialog.fields_dict[field].get_data = function() {
				const data = me.dialog.fields_dict[field].get_value();
				const txt = data.match(/[^,\s*]*$/)[0] || '';
				let options = [];

				frappe.call({
					method: "frappe.email.get_contact_list",
					args: {
						txt: txt,
					},
					callback: (r) => {
						options = r.message;
						me.dialog.fields_dict[field].set_data(options);
					}
				});
				return options;
			}
		});

		this.prepare();
		this.dialog.show();

		if (this.frm) {
			$(document).trigger('form-typing', [this.frm]);
		}

		if (this.cc || this.bcc) {
			this.toggle_more_options(true);
		}
	},

	get_fields: function() {
		let contactList = [];
		let fields = [
			{
				label: __("To"),
				fieldtype: "MultiSelect",
				reqd: 0,
				fieldname: "recipients",
				options: contactList
			},
			{
				fieldtype: "Button",
				label: frappe.utils.icon('down'),
				fieldname: 'option_toggle_button',
				click: () => {
					this.toggle_more_options();
				}
			},
			{
				fieldtype: "Section Break",
				hidden: 1,
				fieldname: "more_options"
			},
			{
				label: __("CC"),
				fieldtype: "MultiSelect",
				fieldname: "cc",
				options: contactList
			},
			{
				label: __("BCC"),
				fieldtype: "MultiSelect",
				fieldname: "bcc",
				options: contactList
			},
			{
				label: __("Email Template"),
				fieldtype: "Link",
				options: "Email Template",
				fieldname: "email_template"
			},
			{ fieldtype: "Section Break" },
			{
				label: __("Subject"),
				fieldtype: "Data",
				reqd: 1,
				fieldname: "subject",
				length: 524288
			},
			{
				label: __("Message"),
				fieldtype: "Text Editor",
				fieldname: "content",
				onchange: frappe.utils.debounce(
					this.save_as_draft.bind(this),
					300
				)
			},
			{ fieldtype: "Section Break" },
			{
				label: __("Send me a copy"),
				fieldtype: "Check",
				fieldname: "send_me_a_copy",
				default: frappe.boot.user.send_me_a_copy
			},
			{
				label: __("Send Read Receipt"),
				fieldtype: "Check",
				fieldname: "send_read_receipt"
			},
			{
				label: __("Attach Document Print"),
				fieldtype: "Check",
				fieldname: "attach_document_print"
			},
			{
				label: __("Select Print Format"),
				fieldtype: "Select",
				fieldname: "select_print_format"
			},
			{
				label: __("Select Languages"),
				fieldtype: "Select",
				fieldname: "language_sel"
			},
			{ fieldtype: "Column Break" },
			{
				label: __("Select Attachments"),
				fieldtype: "HTML",
				fieldname: "select_attachments"
			}
		];

		// add from if user has access to multiple email accounts
		const email_accounts = frappe.boot.email_accounts.filter(account => {
			return (
				!in_list(
					["All Accounts", "Sent", "Spam", "Trash"],
					account.email_account
				) && account.enable_outgoing
			);
		});

		if (frappe.boot.email_accounts && email_accounts.length > 1) {
			fields = [
				{
					label: __("From"),
					fieldtype: "Select",
					reqd: 1,
					fieldname: "sender",
					options: email_accounts.map(function(e) {
						return e.email_id;
					})
				}
			].concat(fields);
		}

		return fields;
	},

	toggle_more_options(show_options) {
		show_options = show_options || this.dialog.fields_dict.more_options.df.hidden;
		this.dialog.set_df_property('more_options', 'hidden', !show_options);
		let label = frappe.utils.icon(show_options ? 'up-line': 'down');
		this.dialog.get_field('option_toggle_button').set_label(label);
	},

	prepare: function() {
		this.setup_subject_and_recipients();
		this.setup_print_language();
		this.setup_print();
		this.setup_attach();
		this.setup_email();
		this.setup_last_edited_communication();
		this.setup_email_template();

		this.dialog.set_value("recipients", this.recipients || '');
		this.dialog.set_value("cc", this.cc || '');
		this.dialog.set_value("bcc", this.bcc || '');

		if(this.dialog.fields_dict.sender) {
			this.dialog.fields_dict.sender.set_value(this.sender || '');
		}
		this.dialog.fields_dict.subject.set_value(
			frappe.utils.html2text(this.subject) || ''
		);

		this.setup_earlier_reply();
	},

	setup_subject_and_recipients: function() {
		this.subject = this.subject || "";

		if(!this.forward && !this.recipients && this.last_email) {
			this.recipients = this.last_email.sender;
			this.cc = this.last_email.cc;
			this.bcc = this.last_email.bcc;
		}

		if(!this.forward && !this.recipients) {
			this.recipients = this.frm && this.frm.timeline.get_recipient();
		}

		if(!this.subject && this.frm) {
			// get subject from last communication
			var last = this.frm.timeline.get_last_email();

			if(last) {
				this.subject = last.subject;
				if(!this.recipients) {
					this.recipients = last.sender;
				}

				// prepend "Re:"
				if(strip(this.subject.toLowerCase().split(":")[0])!="re") {
					this.subject = __("Re: {0}", [this.subject]);
				}
			}

			if (!this.subject) {
				this.subject = this.frm.doc.name;
				if (this.frm.meta.subject_field && this.frm.doc[this.frm.meta.subject_field]) {
					this.subject = this.frm.doc[this.frm.meta.subject_field];
				} else if (this.frm.meta.title_field && this.frm.doc[this.frm.meta.title_field]) {
					this.subject = this.frm.doc[this.frm.meta.title_field];
				}
			}

			// always add an identifier to catch a reply
			// some email clients (outlook) may not send the message id to identify
			// the thread. So as a backup we use the name of the document as identifier
			let identifier = `#${this.frm.doc.name}`;
			if (!this.subject.includes(identifier)) {
				this.subject = `${this.subject} (${identifier})`;
			}
		}

		if (this.frm && !this.recipients) {
			this.recipients = this.frm.doc[this.frm.email_field];
		}
	},

	setup_email_template: function() {
		var me = this;

		this.dialog.fields_dict["email_template"].df.onchange = () => {
			var email_template = me.dialog.fields_dict.email_template.get_value();

			var prepend_reply = function(reply) {
				if(me.reply_added===email_template) {
					return;
				}
				var content_field = me.dialog.fields_dict.content;
				var subject_field = me.dialog.fields_dict.subject;
				var content = content_field.get_value() || "";
				var subject = subject_field.get_value() || "";

				var parts = content.split('<!-- salutation-ends -->');

				if(parts.length===2) {
					content = [reply.message, "<br>", parts[1]];
				} else {
					content = [reply.message, "<br>", content];
				}

				content_field.set_value(content.join(''));

				subject_field.set_value(reply.subject);

				me.reply_added = email_template;
			}

			frappe.call({
				method: 'frappe.email.doctype.email_template.email_template.get_email_template',
				args: {
					template_name: email_template,
					doc: me.frm.doc,
					_lang: me.dialog.get_value("language_sel")
				},
				callback: function(r) {
					prepend_reply(r.message);
				},
			});
		}
	},

	setup_last_edited_communication: function() {
		var me = this;
		if (!this.doc){
			if (cur_frm){
				this.doc = cur_frm.doctype;
			}else{
				this.doc = "Inbox";
			}
		}
		if (cur_frm && cur_frm.docname) {
			this.key = cur_frm.docname;
		} else {
			this.key = "Inbox";
		}
		if(this.last_email) {
			this.key = this.key + ":" + this.last_email.name;
		}
		if(this.subject){
			this.key = this.key + ":" + this.subject;
		}
		this.dialog.onhide = function() {
			var last_edited_communication = me.get_last_edited_communication();
			$.extend(last_edited_communication, {
				sender: me.dialog.get_value("sender"),
				recipients: me.dialog.get_value("recipients"),
				cc: me.dialog.get_value("cc"),
				bcc: me.dialog.get_value("bcc"),
				subject: me.dialog.get_value("subject"),
				content: me.dialog.get_value("content"),
			});

			if (me.frm) {
				$(document).trigger("form-stopped-typing", [me.frm]);
			}
		}

		this.dialog.on_page_show = function() {
			if (!me.txt) {
				var last_edited_communication = me.get_last_edited_communication();
				if(last_edited_communication.content) {
					me.dialog.set_value("sender", last_edited_communication.sender || "");
					me.dialog.set_value("subject", last_edited_communication.subject || "");
					me.dialog.set_value("recipients", last_edited_communication.recipients || "");
					me.dialog.set_value("cc", last_edited_communication.cc || "");
					me.dialog.set_value("bcc", last_edited_communication.bcc || "");
					me.dialog.set_value("content", last_edited_communication.content || "");
				}
			}

		}

	},

	get_last_edited_communication: function() {
		if (!frappe.last_edited_communication[this.doc]) {
			frappe.last_edited_communication[this.doc] = {};
		}

		if(!frappe.last_edited_communication[this.doc][this.key]) {
			frappe.last_edited_communication[this.doc][this.key] = {};
		}

		return frappe.last_edited_communication[this.doc][this.key];
	},

	selected_format: function() {
		return this.dialog.fields_dict.select_print_format.input.value || (this.frm && this.frm.meta.default_print_format) || "Standard";
	},

	get_print_format: function(format) {
		if (!format) {
			format = this.selected_format();
		}

		if (locals["Print Format"] && locals["Print Format"][format]) {
			return locals["Print Format"][format];
		} else {
			return {};
		}
	},

	setup_print_language: function() {
		var doc = this.doc || cur_frm.doc;
		var fields = this.dialog.fields_dict;

		//Load default print language from doctype
		this.lang_code = doc.language

		if (!this.lang_code && this.get_print_format().default_print_language) {
			this.lang_code = this.get_print_format().default_print_language;
		}

		//On selection of language retrieve language code
		var me = this;
		$(fields.language_sel.input).change(function(){
			me.lang_code = this.value
		})

		// Load all languages in the select field language_sel
		$(fields.language_sel.input)
			.empty()
			.add_options(frappe.get_languages());

		if (this.lang_code) {
			$(fields.language_sel.input).val(this.lang_code);
		}
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
			const print_formats = frappe.meta.get_print_formats(cur_frm.meta.name);
			$(fields.select_print_format.input)
				.empty()
				.add_options(print_formats)
				.val(print_formats[0]);
		} else {
			$(fields.attach_document_print.wrapper).toggle(false);
		}

	},

	setup_attach: function() {
		var fields = this.dialog.fields_dict;
		var attach = $(fields.select_attachments.wrapper);

		if (!this.attachments) {
			this.attachments = [];
		}

		let args = {
			folder: 'Home/Attachments',
			on_success: attachment => {
				this.attachments.push(attachment);
				this.render_attachment_rows(attachment);
			}
		};

		if (this.frm) {
			args = {
				doctype: this.frm.doctype,
				docname: this.frm.docname,
				folder: 'Home/Attachments',
				on_success: attachment => {
					this.frm.attachments.attachment_uploaded(attachment);
					this.render_attachment_rows(attachment);
				}
			};
		}

		$(`
			<label class="control-label">
				${__("Select Attachments")}
			</label>
			<div class='attach-list'></div>
			<p class='add-more-attachments'>
				<button class='btn btn-xs btn-default'>
					${frappe.utils.icon('small-add', 'xs')}&nbsp;
					${__("Add Attachment")}
				</button>
			</p>
		`).appendTo(attach.empty());

		attach
			.find(".add-more-attachments button")
			.on('click', () => new frappe.ui.FileUploader(args));
		this.render_attachment_rows();
	},

	render_attachment_rows: function(attachment) {
		const select_attachments = this.dialog.fields_dict.select_attachments;
		const attachment_rows = $(select_attachments.wrapper).find(".attach-list");
		if (attachment) {
			attachment_rows.append(this.get_attachment_row(attachment, true));
		} else {
			let files = [];
			if (this.attachments && this.attachments.length) {
				files = files.concat(this.attachments);
			}
			if (this.frm) {
				files = files.concat(this.frm.get_files());
			}

			if (files.length) {
				$.each(files, (i, f) => {
					if (!f.file_name) return;
					if (!attachment_rows.find(`[data-file-name="${f.name}"]`).length) {
						f.file_url = frappe.urllib.get_full_url(f.file_url);
						attachment_rows.append(this.get_attachment_row(f));
					}
				});
			}
		}
	},

	get_attachment_row(attachment, checked) {
		return $(`<p class="checkbox flex">
			<label class="ellipsis" title="${attachment.file_name}">
				<input
					type="checkbox"
					data-file-name="${attachment.name}"
					${checked ? 'checked': ''}>
				</input>
				<span class="ellipsis">${attachment.file_name}</span>
			</label>
			&nbsp;
			<a href="${attachment.file_url}" target="_blank" class="btn-linkF">
				${frappe.utils.icon('link-url')}
			</a>
		</p>`);
	},

	setup_email: function() {
		// email
		var fields = this.dialog.fields_dict;

		if(this.attach_document_print) {
			$(fields.attach_document_print.input).click();
			$(fields.select_print_format.wrapper).toggle(true);
		}

		$(fields.send_me_a_copy.input).on('click', () => {
			// update send me a copy (make it sticky)
			let val = fields.send_me_a_copy.get_value();
			frappe.db.set_value('User', frappe.session.user, 'send_me_a_copy', val);
			frappe.boot.user.send_me_a_copy = val;
		});

	},

	send_action: function() {
		var me = this;
		var btn = me.dialog.get_primary_btn();

		var form_values = this.get_values();
		if(!form_values) return;

		var selected_attachments =
			$.map($(me.dialog.wrapper).find("[data-file-name]:checked"), function (element) {
				return $(element).attr("data-file-name");
			});


		if(form_values.attach_document_print) {
			me.send_email(btn, form_values, selected_attachments, null, form_values.select_print_format || "");
		} else {
			me.send_email(btn, form_values, selected_attachments);
		}
	},

	get_values: function() {
		var form_values = this.dialog.get_values();

		// cc
		for ( var i=0, l=this.dialog.fields.length; i < l; i++ ) {
			var df = this.dialog.fields[i];

			if ( df.is_cc_checkbox ) {
				// concat in cc
				if ( form_values[df.fieldname] ) {
					form_values.cc = ( form_values.cc ? (form_values.cc + ", ") : "" ) + df.fieldname;
					form_values.bcc = ( form_values.bcc ? (form_values.bcc + ", ") : "" ) + df.fieldname;
				}

				delete form_values[df.fieldname];
			}
		}

		return form_values;
	},

	save_as_draft: function() {
		if (this.dialog && this.frm) {
			let message = this.dialog.get_value('content');
			message = message.split(frappe.separator_element)[0];
			localforage.setItem(this.frm.doctype + this.frm.docname, message).catch(e => {
				if (e) {
					// silently fail
					console.log(e); // eslint-disable-line
					console.warn('[Communication] localStorage is full. Cannot save message as draft'); // eslint-disable-line
				}
			});

		}
	},

	delete_saved_draft() {
		if (this.dialog) {
			localforage.removeItem(this.frm.doctype + this.frm.docname).catch(e => {
				if (e) {
					// silently fail
					console.log(e); // eslint-disable-line
					console.warn('[Communication] localStorage is full. Cannot save message as draft'); // eslint-disable-line
				}
			});
		}
	},

	send_email: function(btn, form_values, selected_attachments, print_html, print_format) {
		var me = this;
		me.dialog.hide();

		if(!form_values.recipients) {
			frappe.msgprint(__("Enter Email Recipient(s)"));
			return;
		}

		if(!form_values.attach_document_print) {
			print_html = null;
			print_format = null;
		}


		if(cur_frm && !frappe.model.can_email(me.doc.doctype, cur_frm)) {
			frappe.msgprint(__("You are not allowed to send emails related to this document"));
			return;
		}


		return frappe.call({
			method:"frappe.core.doctype.communication.email.make",
			args: {
				recipients: form_values.recipients,
				cc: form_values.cc,
				bcc: form_values.bcc,
				subject: form_values.subject,
				content: form_values.content,
				doctype: me.doc.doctype,
				name: me.doc.name,
				send_email: 1,
				print_html: print_html,
				send_me_a_copy: form_values.send_me_a_copy,
				print_format: print_format,
				sender: form_values.sender,
				sender_full_name: form_values.sender?frappe.user.full_name():undefined,
				email_template: form_values.email_template,
				attachments: selected_attachments,
				_lang : me.lang_code,
				read_receipt:form_values.send_read_receipt,
				print_letterhead: me.is_print_letterhead_checked(),
			},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					frappe.utils.play_sound("email");

					if(r.message["emails_not_sent_to"]) {
						frappe.msgprint(__("Email not sent to {0} (unsubscribed / disabled)",
							[ frappe.utils.escape_html(r.message["emails_not_sent_to"]) ]) );
					}

					if ((frappe.last_edited_communication[me.doc] || {})[me.key]) {
						delete frappe.last_edited_communication[me.doc][me.key];
					}
					if (cur_frm) {
						cur_frm.reload_doc();
					}

					// try the success callback if it exists
					if (me.success) {
						try {
							me.success(r);
						} catch (e) {
							console.log(e);
						}
					}

				} else {
					frappe.msgprint(__("There were errors while sending email. Please try again."));

					// try the error callback if it exists
					if (me.error) {
						try {
							me.error(r);
						} catch (e) {
							console.log(e);
						}
					}
				}
			}
		});
	},

	is_print_letterhead_checked: function() {
		if (this.frm && $(this.frm.wrapper).find('.form-print-wrapper').is(':visible')){
			return $(this.frm.wrapper).find('.print-letterhead').prop('checked') ? 1 : 0;
		} else {
			return (frappe.model.get_doc(":Print Settings", "Print Settings") ||
				{ with_letterhead: 1 }).with_letterhead ? 1 : 0;
		}
	},

	get_default_outgoing_email_account_signature: function() {
		return frappe.db.get_value('Email Account', { 'default_outgoing': 1, 'add_signature': 1 }, 'signature');
	},

	setup_earlier_reply: async function() {
		let fields = this.dialog.fields_dict;
		let signature = frappe.boot.user.email_signature || "";

		if (!signature) {
			const res = await this.get_default_outgoing_email_account_signature();
			signature = res.message.signature;
		}

		if (signature && !frappe.utils.is_html(signature)) {
			signature = signature.replace(/\n/g, "<br>");
		}

		if(this.txt) {
			this.message = this.txt + (this.message ? ("<br><br>" + this.message) : "");
		} else {
			// saved draft in localStorage
			const { doctype, docname } = this.frm || {};
			if (doctype && docname) {
				this.message = await localforage.getItem(doctype + docname) || '';
			}
		}

		if(this.real_name) {
			this.message = '<p>'+__('Dear') +' '
				+ this.real_name + ",</p><!-- salutation-ends --><br>" + (this.message || "");
		}

		if(this.message && signature && this.message.includes(signature)) {
			signature = "";
		}

		let reply = (this.message || "") + (signature ? ("<br>" + signature) : "");
		let content = '';

		if (this.is_a_reply === 'undefined') {
			this.is_a_reply = true;
		}

		if (this.is_a_reply) {
			let last_email = this.last_email;

			if (!last_email) {
				last_email = this.frm && this.frm.timeline.get_last_email(true);
			}

			if (!last_email) return;

			let last_email_content = last_email.original_comment || last_email.content;

			// convert the email context to text as we are enclosing
			// this inside <blockquote>
			last_email_content = this.html2text(last_email_content).replace(/\n/g, '<br>');

			// clip last email for a maximum of 20k characters
			// to prevent the email content from getting too large
			if (last_email_content.length > 20 * 1024) {
				last_email_content += '<div>' + __('Message clipped') + '</div>' + last_email_content;
				last_email_content = last_email_content.slice(0, 20 * 1024);
			}

			let communication_date = last_email.communication_date || last_email.creation;
			content = `
				<div><br></div>
				${reply}
				${frappe.separator_element || ''}
				<p>${__("On {0}, {1} wrote:", [frappe.datetime.global_date_format(communication_date) , last_email.sender])}</p>
				<blockquote>
				${last_email_content}
				</blockquote>
			`;
		} else {
			content = "<div><br></div>" + reply;
		}
		fields.content.set_value(content);
	},

	html2text: function(html) {
		// convert HTML to text and try and preserve whitespace
		var d = document.createElement( 'div' );
		d.innerHTML = html.replace(/<\/div>/g, '<br></div>')  // replace end of blocks
			.replace(/<\/p>/g, '<br></p>') // replace end of paragraphs
			.replace(/<br>/g, '\n');
		let text = d.textContent;

		// replace multiple empty lines with just one
		return text.replace(/\n{3,}/g, '\n\n');
	}
});
