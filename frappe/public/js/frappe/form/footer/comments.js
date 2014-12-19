// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Comments = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $(frappe.render_template("timeline",
			{ image: frappe.user_info(user).image, fullname: user_fullname })).appendTo(this.parent);

			this.list = this.wrapper.find(".timeline-items");

		this.input = this.wrapper.find(".form-control");
		this.button = this.wrapper.find(".btn-go")
			.click(function() {
				if(me.wrapper.find(".is-email").prop("checked")) {
					new frappe.views.CommunicationComposer({
						doc: me.frm.doc,
						txt: me.input.val(),
						frm: me.frm
					})
				} else {
					me.add_comment(this);
				}
			});
	},
	refresh: function(scroll_to_end) {
		var me = this,
			last_type = "Comment";
		if(this.frm.doc.__islocal) {
			this.wrapper.toggle(false);
			return;
		}
		this.wrapper.toggle(true);
		this.list.empty();

		var comments = [{"comment": __("Created"), "comment_type": "Created",
			"comment_by": this.frm.doc.owner, "creation": this.frm.doc.creation}].concat(this.get_comments());

		$.each(comments.sort(function(a, b) { return a.creation > b.creation ? -1 : 1 }),
			function(i, c) {
				me.render_comment(c);
		});

		this.wrapper.find(".is-email").prop("checked", last_type==="Email");

		if(scroll_to_end) {
			scroll(0, $(this.frm.wrapper).find(".form-comments .btn-go").offset().top);
		}
		this.update_sidebar_comments();

	},
	render_comment: function(c) {
		var me = this;
		if((c.comment_type || "Comment") === "Comment" && frappe.model.can_delete("Comment")) {
			c["delete"] = '<a class="close" href="#">&times;</a>';
		} else {
			c["delete"] = "";
		}

		if(c.comment_by.indexOf("<")!==-1) {
			c.comment_by = c.comment_by.split("<")[1].split(">")[0];
		}

		c.image = frappe.user_info(c.comment_by).image
			|| frappe.get_gravatar(c.comment_by);
		c.comment_on = comment_when(c.creation);
		c.fullname = frappe.user_info(c.comment_by).fullname;

		if(c.attachments && typeof c.attachments==="string")
			c.attachments = JSON.parse(c.attachments);

		if(!c.comment_type)
			c.comment_type = "Comment"

		this.set_icon_and_color(c);

		// label view
		if(c.comment_type==="Workflow" || c.comment_type==="Label") {
			c.comment_html = repl('<span class="label label-%(style)s">%(text)s</span>', {
				style: frappe.utils.guess_style(c.comment),
				text: __(c.comment)
			});
		} else {
			if(c.comment_type=="Email") {
				c.comment = c.comment.split("-----"+__("In response to")+"-----")[0];
				c.comment = frappe.utils.strip_original_content(c.comment);
				c.comment = frappe.utils.remove_script_and_style(c.comment);
			}

			if(!frappe.utils.is_html(c.comment)) {
				c.comment_html = frappe.markdown(__(c.comment));
			} else {
				c.comment_html = c.comment;
				c.comment_html = frappe.utils.strip_whitespace(c.comment_html);
			}
		}

		// icon centering -- pixed perfect
		if(in_list(["Comment", "Email", "Assignment Completed"], c.comment_type)) {
			c.padding = "padding-left: 8px;";
		} else if(in_list(["Created"], c.comment_type)) {
			c.padding = "padding-left: 9px;";
		} else {
			c.padding = "";
		}

		$(frappe.render_template("timeline_item", {data:c}))
			.appendTo(me.list)
			.on("click", ".close", function() {
				var name = $(this).parents(".comment:first").attr("data-name");
				me.delete_comment(name);
				return false;
			});

		if(c.comment_type==="Email") {
			last_type = c.comment_type;
		}

	},
	set_icon_and_color: function(c) {
		c.icon = {
			"Email": "icon-envelope",
			"Chat": "icon-comments",
			"Phone": "icon-phone",
			"SMS": "icon-mobile-phone",
			"Created": "icon-plus",
			"Submitted": "icon-lock",
			"Cancelled": "icon-remove",
			"Assigned": "icon-user",
			"Assignment Completed": "icon-ok",
			"Comment": "icon-comment",
			"Workflow": "icon-arrow-right",
			"Label": "icon-tag",
			"Attachment": "icon-paper-clip",
			"Attachment Removed": "icon-paper-clip"
		}[c.comment_type]

		c.color = {
			"Email": "#3498db",
			"Chat": "#3498db",
			"Phone": "#3498db",
			"SMS": "#3498db",
			"Created": "#1abc9c",
			"Submitted": "#1abc9c",
			"Cancelled": "#c0392b",
			"Assigned": "#f39c12",
			"Assignment Completed": "#16a085",
			"Comment": "#f39c12",
			"Workflow": "#2c3e50",
			"Label": "#2c3e50",
			"Attachment": "#7f8c8d",
			"Attachment Removed": "#eee"
		}[c.comment_type];

		c.icon_fg = {
			"Attachment Removed": "#333",
		}[c.comment_type]

		if(!c.icon_fg)
			c.icon_fg = "#fff";

	},
	update_sidebar_comments: function() {
		var comments = $.map(this.get_comments(), function(c) {
			return (c.comment_type==="Email" || c.comment_type==="Comment") ? c : null;
		});
		this.frm.sidebar.wrapper.find(".n-comments").html(comments.length);
	},
	get_comments: function() {
		return this.frm.get_docinfo().comments;
	},
	add_comment: function(btn) {
		var txt = this.input.val();

		if(txt) {
			this.insert_comment("Comment", txt, btn);
		}
	},
	insert_comment: function(comment_type, comment, btn) {
		var me = this;
		return frappe.call({
			method: "frappe.desk.form.utils.add_comment",
			args: {
				doc:{
					doctype: "Comment",
					comment_type: comment_type || "Comment",
					comment_doctype: this.frm.doctype,
					comment_docname: this.frm.docname,
					comment: comment,
					comment_by: user
				}
			},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					me.frm.get_docinfo().comments =
						me.get_comments().concat([r.message]);
					me.frm.toolbar.show_infobar();
					me.input.val("");
					me.refresh(true);
				}
			}
		});

	},

	delete_comment: function(name) {
		var me = this;
		return frappe.call({
			method: "frappe.client.delete",
			args: {
				doctype: "Comment",
				name: name
			},
			callback: function(r) {
				if(!r.exc) {
					me.frm.get_docinfo().comments =
						$.map(me.frm.get_docinfo().comments,
							function(v) {
								if(v.name==name) return null;
								else return v;
							}
						);
					me.refresh(true);
					me.frm.toolbar.show_infobar();
				}
			}
		});
	},

	get_recipient: function() {
		if(this.frm.email_field) {
			return this.frm.doc[this.frm.email_field];
		} else {
			return this.frm.doc.email_id || this.frm.doc.email || "";
		}
	},

	get_last_email: function(from_recipient) {
		var last_email = null,
			comments = this.frm.get_docinfo().comments,
			email = this.get_recipient();

		$.each(comments.sort(function(a, b) { return a.creation > b.creation ? -1 : 1 }), function(i, c) {
			if(c.comment_type=="Email") {
				if(from_recipient) {
					if(c.comment_by.indexOf(email)!==-1) {
						last_email = c;
						return false;
					}
				} else {
					last_email = c;
					return false;
				}
			}
		});

		return last_email;
	}
})
