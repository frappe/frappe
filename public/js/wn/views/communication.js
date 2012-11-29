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
			email: this.email
		})
	},

	prepare: function(doc) {
		//doc.when = comment_when(this.doc.modified);
		doc.when = doc.modified;
		if(doc.content.indexOf("<br>")== -1 && doc.content.indexOf("<p>")== -1) {
			doc.content = doc.content.replace(/\n/g, "<br>");
		}
		if(!doc.sender) doc.sender = "[unknown sender]";
		doc.sender = doc.sender.replace(/</, "&lt;").replace(/>/, "&gt;");
		doc.content = doc.content.split("-----In response to-----")[0];
		doc.content = doc.content.split("-----Original Message-----")[0];
	},
	make_line: function(doc) {
		var me = this;
		var comm = $(repl('<tr><td title="Click to Expand / Collapse">\
				<p><b>%(sender)s on %(when)s</b> \
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
			fields: [
				{label:"To", fieldtype:"Data", reqd: 1, fieldname:"sender"},
				{label:"Subject", fieldtype:"Data", reqd: 1},
				{label:"Message", fieldtype:"Text Editor", reqd: 1, fieldname:"content"},
				{label:"Add Reply", fieldtype:"Button"},
				{label:"Send Email", fieldtype:"Check"},
				{label:"Attach Document Print", fieldtype:"Check"},
				{label:"Select Print Format", fieldtype:"Select"},
				{label:"Select Attachments", fieldtype:"HTML"}
			]
		});
		this.prepare();
	},
	prepare: function() {
		this.setup_print();
		this.setup_email();
		$(this.dialog.fields_dict.sender.input).val(this.email || "").change();
		$(this.dialog.fields_dict.subject.input).val(this.subject || "").change();
		this.setup_earlier_reply();		
	},
	setup_print: function() {
		// print formats
		var fields = this.dialog.fields_dict;
		
		// toggle print format
		$(fields.attach_document_print.input).click(function() {
			$(fields.select_print_format.wrapper).toggle($(this).is(":checked"));
			$(fields.select_attachments.wrapper).toggle($(this).is(":checked"));
		});

		// select print format
		$(fields.select_print_format.wrapper).toggle(false);
		$(fields.select_print_format.input)
			.empty()
			.add_options(cur_frm.print_formats);
			
		// show attachment list
		var attach = $(fields.select_attachments.wrapper);
		attach.toggle(false);
		
		$.each(cur_frm.get_files(), function(i, f) {
			$(repl("<p><input type='checkbox' \
				data-file-name='%(file)s'> %(file)s</p>", {file:f})).appendTo(attach)
		});
	},
	setup_email: function() {
		// email
		var me = this;
		var fields = this.dialog.fields_dict;
		
		$(fields.send_email.input).attr("checked", "checked")
		$(fields.add_reply.input).click(function() {
			var args = me.dialog.get_values();
			if(!args) return;
			
			_p.build(args.select_print_format || "", function(print_html) {
				$(this).set_working();
				wn.call({
					method:"support.doctype.communication.communication.make",
					args: {
						sender: args.sender,
						subject: args.subject,
						content: args.content,
						doctype: me.doc.doctype,
						name: me.doc.name,
						lead: me.doc.lead,
						contact: me.doc.contact,
						recipients: me.email,
						print_html: args.attach_document_print
							? print_html : "",
						
					},
					callback: function(r) {
						me.dialog.hide();
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
			
		if(comm_list.length > 0) {
			fields.content.input.set_input("<p></p>"
				+ (wn.boot.profile.email_signature || "")
				+"<p></p>"
				+"-----In response to-----<p></p>" 
				+ comm_list[0].content);
		} else {
			fields.content.input.set_input("<p></p>"
				+ (wn.boot.profile.email_signature || ""))
		}
	}
})
