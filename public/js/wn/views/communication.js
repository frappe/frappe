// for license information, see license.txt

// opts - parent, list, doc, email
wn.views.CommunicationList = Class.extend({
	init: function(opts) {
		this.comm_list = [];
		$.extend(this, opts);
				
		if(this.doc.__islocal) {
			return;
		}
		
		this.list.sort(function(a, b) { return 
			(new Date(a.modified) > new Date(b.modified)) 
			? -1 : 1; })
				
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
			this.body.remove()
			$("<div class='alert'>No Communication with this " 
				+ this.doc.doctype +" yet.</div>").appendTo(this.wrapper);
		}
		
	},
	make_body: function() {
		$(this.parent)
			.html("")
			.css({"margin":"10px 0px"});
			
		this.wrapper = $("<div><h4>Communication History</h4>\
			<div style='margin-bottom: 8px;'>\
				<button class='btn btn-small' \
					onclick='cur_frm.communication_view.add_reply()'>\
				<i class='icon-plus'></i> Add Reply</button></div>\
			</div>")
			.appendTo(this.parent);
			
		this.body = $("<table class='table table-bordered table-hover table-striped'>")
			.appendTo(this.wrapper);
	},
	
	add_reply: function() {
		new wn.views.CommunicationComposer({
			doc: this.doc,
			subject: this.doc.subject,
			recipients: this.recipients
		})
	},

	prepare: function(doc) {
		//doc.when = comment_when(this.doc.modified);
		doc.when = doc.modified;
		if(doc.content.indexOf("<br>")== -1 && doc.content.indexOf("<p>")== -1) {
			doc.content = doc.content.replace(/\n/g, "<br>");
		}
		if(!doc.sender) doc.sender = "[unknown sender]";
		doc._sender = doc.sender.replace(/</, "&lt;").replace(/>/, "&gt;");
		doc.content = doc.content.split("-----In response to-----")[0];
		doc.content = doc.content.split("-----Original Message-----")[0];
	},
	
	make_line: function(doc) {
		var me = this;
		var comm = $(repl('<tr><td title="Click to Expand / Collapse">\
				<p><b>%(_sender)s on %(when)s</b> \
					<a href="#Form/Communication/%(name)s" style="font-size: 90%">\
						Show Details</a></p>\
				<div class="comm-content" style="border-top: 1px solid #ddd; \
					padding: 10px; overflow-x: auto; display: none;"></div>\
			</td></tr>', doc))
			.appendTo(this.body)
			.css({"cursor":"pointer"})
			.click(function() {
				$(this).find(".comm-content").toggle();
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
		this.dialog = new wn.ui.Dialog({
			width: 640,
			title: "Add Reply: " + (this.subject || ""),
			no_submit_on_enter: true,
			fields: [
				{label:"To", fieldtype:"Data", reqd: 1, fieldname:"recipients"},
				{label:"Subject", fieldtype:"Data", reqd: 1},
				{label:"Message", fieldtype:"Text Editor", reqd: 1, fieldname:"content"},
				{label:"Add Reply", fieldtype:"Button"},
				{label:"Send Email", fieldtype:"Check"},
				{label:"Send Me A Copy", fieldtype:"Check"},
				{label:"Attach Document Print", fieldtype:"Check"},
				{label:"Select Print Format", fieldtype:"Select"},
				{label:"Select Attachments", fieldtype:"HTML"}
			]
		});
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
			$(fields.select_print_format.wrapper).toggle($(this).is(":checked"));
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
		if(files) {
			$("<p><b>Add Attachments:</b></p>").appendTo(attach);
			$.each(cur_frm.get_files(), function(i, f) {
				$(repl("<p><input type='checkbox' \
					data-file-name='%(file)s'> %(file)s</p>", {file:f})).appendTo(attach)
			});
		}
	},
	setup_email: function() {
		// email
		var me = this;
		var fields = this.dialog.fields_dict;
		
		$(fields.send_email.input).attr("checked", "checked")
		$(fields.add_reply.input).click(function() {
			var form_values = me.dialog.get_values();
			if(!form_values) return;
					
			var selected_attachments = $.map($(me.dialog.wrapper)
				.find("[data-file-name]:checked"), function(element) {
					return $(element).attr("data-file-name");
				})
						
			_p.build(args.select_print_format || "", function(print_html) {
				me.dialog.hide();
				wn.call({
					method:"core.doctype.communication.communication.make",
					args: {
						sender: wn.user_info(user).fullname + " <" + wn.boot.profile.email + ">",
						recipients: form_values.recipients,
						subject: form_values.subject,
						content: form_values.content,
						doctype: me.doc.doctype,
						name: me.doc.name,
						lead: me.doc.lead,
						contact: me.doc.contact,
						send_me_a_copy: form_values.send_me_a_copy,
						send_email: form_values.send_email,
						print_html: form_values.attach_document_print
							? print_html : "",
						attachments: selected_attachments
					},
					callback: function(r) {
						cur_frm.reload_doc();
					}
				});				
			})
		});		
	},
	setup_earlier_reply: function() {
		var fields = this.dialog.fields_dict;
		var comm_list = cur_frm.communication_view
			? cur_frm.communication_view.list
			: [];
		var signature = wn.boot.profile.email_signature || "";
		if(signature.indexOf("<br>")==-1 && signature.indexOf("<p")==-1 
			&& signature.indexOf("<img")==-1 && signature.indexOf("<div")==-1) {
			signature = signature.replace(/\n/g, "<br>");
		}
		
		if(comm_list.length > 0) {
			fields.content.input.set_input("<p></p>"
				+ signature
				+"<p></p>"
				+"-----In response to-----<p></p>" 
				+ comm_list[0].content);
		} else {
			fields.content.input.set_input("<p></p>" + signature)
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
					wn.call({
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

