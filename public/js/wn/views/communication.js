// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt

// opts - parent, list, doc, email
wn.views.CommunicationList = Class.extend({
	init: function(opts) {
		this.comm_list = [];
		$.extend(this, opts);
				
		if(this.doc.__islocal) {
			$(this.parent).empty();
			return;
		}
		
		var sortfn = function (a, b) { return (b.creation > a.creation) ? 1 : -1; }
		this.list = this.list.sort(sortfn);

		this.make();
	},
	make: function() {
		var me = this;
		this.make_body();

		if(this.list && this.list.length) {
			$.each(this.list, function(i, d) {
				me.prepare(d);
				me.make_line(d);
			});			
			// show first
			this.comm_list[0].find('.comm-content').toggle(true);			
		} else {
			this.clear_list()
		}
	},
	clear_list: function() {
		this.body.remove();
		$("<div class='alert alert-info'>" + wn._("No Communication tagged with this ") 
			+ this.doc.doctype +" yet.</div>").appendTo(this.wrapper);	
	},
	make_body: function() {
		$(this.parent)
			.empty()
			.css({"margin":"10px 0px"});
			
		this.wrapper = $("<div>\
			<div style='margin-bottom: 8px;'>\
				<button class='btn btn-default' \
					onclick='cur_frm.communication_view.add_reply()'>\
				<i class='icon-plus'></i> "+wn._("Add Message")+"</button></div>\
			</div>")
			.appendTo(this.parent);
			
		this.body = $("<table class='table table-bordered table-hover table-striped'>")
			.appendTo(this.wrapper);
	},
	
	add_reply: function() {
		var subject = this.doc.subject;
		if(!subject && this.list.length) {
			// get subject from previous message
			subject = this.list[0].subject || "[No Subject]";
			if(strip(subject.toLowerCase().split(":")[0])!="re") {
				subject = "Re: " + subject;
			}
		}
		new wn.views.CommunicationComposer({
			doc: this.doc,
			subject: subject,
			recipients: this.recipients
		})
	},

	prepare: function(doc) {
		//doc.when = comment_when(this.doc.modified);
		doc.when = doc.modified;
		if(!doc.content) doc.content = "[no content]";
		if(!wn.utils.is_html(doc.content)) {
			doc.content = doc.content.replace(/\n/g, "<br>");
		}
		doc.content = wn.utils.remove_script_and_style(doc.content);

		if(!doc.sender) doc.sender = "[unknown sender]";
		doc._sender = doc.sender.replace(/</, "&lt;").replace(/>/, "&gt;");
		doc.content = doc.content.split("-----"+wn._("In response to")+"-----")[0];
		doc.content = doc.content.split("-----"+wn._("Original Message")+"-----")[0];
	},
	
	make_line: function(doc) {
		var me = this;
		var comm = $(repl('<tr><td>\
				<a href="#Form/Communication/%(name)s" class="show-details" style="font-size: 90%; float: right;">'
					+wn._('Show Details')+'</a>\
				<p class="comm-header" title="'+wn._('Click to Expand / Collapse')+'">\
					<b>%(_sender)s on %(when)s</b></p>\
				<div class="comm-content" style="border-top: 1px solid #ddd; \
					padding: 10px; overflow-x: auto; display: none;"></div>\
			</td></tr>', doc))
			.appendTo(this.body);
		
		if(!doc.name) {
			comm.find(".show-details").toggle(false);
		}
			
		comm.find(".comm-header")
			.css({"cursor":"pointer"})
			.click(function() {
				$(this).parent().find(".comm-content").toggle();
			});
		
		this.comm_list.push(comm);
		comm.find(".comm-content").html(doc.content);
	}
});

wn.views.CommunicationComposer = Class.extend({
	init: function(opts) {
		$.extend(this, opts)
		this.make();
		this.dialog.show();
	},
	make: function() {
		var me = this;
		this.dialog = new wn.ui.Dialog({
			width: 640,
			title: wn._("Add Reply") + ": " + (this.subject || ""),
			no_submit_on_enter: true,
			fields: [
				{label:wn._("To"), fieldtype:"Data", reqd: 1, fieldname:"recipients", 
					description:wn._("Email addresses, separted by commas")},
				{label:wn._("Subject"), fieldtype:"Data", reqd: 1, 
					fieldname:"subject"},
				{label:wn._("Send"), fieldtype:"Button", 
					fieldname:"send"},
				{label:wn._("Message"), fieldtype:"Text Editor", reqd: 1, 
					fieldname:"content"},
				{label:wn._("Send Email"), fieldtype:"Check",
					fieldname:"send_email"},
				{label:wn._("Send Me A Copy"), fieldtype:"Check",
					fieldname:"send_me_a_copy"},
				{label:wn._("Attach Document Print"), fieldtype:"Check",
					fieldname:"attach_document_print"},
				{label:wn._("Select Print Format"), fieldtype:"Select",
					fieldname:"select_print_format"},
				{label:wn._("Select Attachments"), fieldtype:"HTML",
					fieldname:"select_attachments"}
			]
		});
		$(document).on("upload_complete", function(event, filename, fileurl) {
			if(me.dialog.display) {
				var wrapper = $(me.dialog.fields_dict.select_attachments.wrapper);

				// find already checked items
				var checked_items = wrapper.find('[data-file-name]:checked').map(function() {
					return $(this).attr("data-file-name");
				});
				
				// reset attachment list
				me.setup_attach();
				
				// check latest added
				checked_items.push(filename);
				
				$.each(checked_items, function(i, filename) {
					wrapper.find('[data-file-name="'+ filename +'"]').prop("checked", true);
				});
			}
		})
		this.prepare();
	},
	prepare: function() {
		this.setup_print();
		this.setup_attach();
		this.setup_email();
		this.setup_autosuggest();
		$(this.dialog.fields_dict.recipients.input).val(this.recipients || "").change();
		$(this.dialog.fields_dict.subject.input).val(this.subject || "").change();
		this.setup_earlier_reply();
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
		$(fields.select_print_format.input)
			.empty()
			.add_options(cur_frm.print_formats)
			.val(cur_frm.print_formats[0]);
			
	},
	setup_attach: function() {
		var fields = this.dialog.fields_dict;
		var attach = $(fields.select_attachments.wrapper);
		
		var files = cur_frm.get_files();
		if(files.length) {
			$("<p><b>"+wn._("Add Attachments")+":</b></p>").appendTo(attach.empty());
			$.each(files, function(i, f) {
				$(repl("<p><input type='checkbox' \
					data-file-name='%(file)s'> %(file)s</p>", {file:f})).appendTo(attach)
			});
		}
	},
	setup_email: function() {
		// email
		var me = this;
		var fields = this.dialog.fields_dict;
		
		if(this.attach_document_print) {
			$(fields.send_me_a_copy.input).click();
			$(fields.attach_document_print.input).click();
			$(fields.select_print_format.wrapper).toggle(true);
		}
		
		$(fields.send_email.input).prop("checked", true)
		$(fields.send.input).click(function() {
			var btn = this;
			var form_values = me.dialog.get_values();
			if(!form_values) return;
					
			var selected_attachments = $.map($(me.dialog.wrapper)
				.find("[data-file-name]:checked"), function(element) {
					return $(element).attr("data-file-name");
				})
			
			if(form_values.attach_document_print) {
				_p.build(form_values.select_print_format || "", function(print_format_html) {
					me.send_email(btn, form_values, selected_attachments, print_format_html);
				});
			} else {
				me.send_email(btn, form_values, selected_attachments);
			}
		});
	},
	
	send_email: function(btn, form_values, selected_attachments, print_format_html) {
		var me = this;
		
		if(form_values.attach_document_print) {
			var print_html = print_format_html;
			if(cint(wn.boot.send_print_in_body_and_attachment)) {
				form_values.content = form_values.content 
					+ "<p></p><hr>" + print_html;
			} else {
				form_values.content = form_values.content + "<p>"
					+ "Please see attachment for document details.</p>"
			}
		} else {
			var print_html = "";
		}
		
		return wn.call({
			method:"core.doctype.communication.communication.make",
			args: {
				sender: [wn.user_info(user).fullname, wn.boot.profile.email],
				recipients: form_values.recipients,
				subject: form_values.subject,
				content: form_values.content,
				doctype: me.doc.doctype,
				name: me.doc.name,
				lead: me.doc.lead,
				contact: me.doc.contact,
				company: me.doc.company || wn.defaults.get_default("company"),
				send_me_a_copy: form_values.send_me_a_copy,
				send_email: form_values.send_email,
				print_html: print_html,
				attachments: selected_attachments
			},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					if(form_values.send_email)
						msgprint("Email sent to " + form_values.recipients);
					me.dialog.hide();
					cur_frm.reload_doc();
				} else {
					msgprint("There were errors while sending email. Please try again.")
				}
			}
		});
	},
	
	setup_earlier_reply: function() {
		var fields = this.dialog.fields_dict;
		var comm_list = cur_frm.communication_view
			? cur_frm.communication_view.list
			: [];
		var signature = wn.boot.profile.email_signature || "";

		if(!wn.utils.is_html(signature)) {
			signature = signature.replace(/\n/g, "<br>");
		}
		
		if(this.real_name) {
			this.message = '<p>'+wn._('Dear') +' ' + this.real_name + ",</p>" + (this.message || "");
		}
		
		if(comm_list.length > 0) {
			fields.content.set_input((this.message || "") + 
				"<p></p>"
				+ signature
				+"<p></p>"
				+"-----"+wn._("In response to")+"-----<p></p>" 
				+ comm_list[0].content);
		} else {
			fields.content.set_input((this.message || "") 
				+ "<p></p>" + signature)
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
						$(this).data( "autocomplete" ).menu.active ) {
					event.preventDefault();
				}
			})	
			.autocomplete({
				source: function(request, response) {
					return wn.call({
						method:'webnotes.utils.email_lib.get_contact_list',
						args: {
							'select': "email_id", 
							'from': "Contact", 
							'where': "email_id", 
							'txt': extractLast(request.term).value || '%'
						},
						callback: function(r) {
							response($.ui.autocomplete.filter(
								r.cl || [], extractLast(request.term)));
						}
					});
				},
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

