// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
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
			.on("click", function() {
				if(me.wrapper.find(".is-email").prop("checked")) {
					new frappe.views.CommunicationComposer({
						doc: me.frm.doc,
						txt: frappe.markdown(me.input.val()),
						frm: me.frm,
						recipients: me.get_recipient()
					})
				} else {
					me.add_comment(this);
				}
			});

		this.email_check = this.wrapper.find(".timeline-head input[type='checkbox']")
			.on("change", function() {
				me.button.html($(this).prop("checked") ? __("Compose") : __("Comment"));
			});

		this.list.on("click", ".toggle-blockquote", function() {
			$(this).parent().siblings("blockquote").toggleClass("hidden");
		});
	},
	refresh: function(scroll_to_end) {
		var me = this;

		this.last_type = "Comment";

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
				if(c.comment) me.render_comment(c);
		});

		this.wrapper.find(".is-email").prop("checked", this.last_type==="Email").change();

		this.frm.sidebar.refresh_comments();

	},
	render_comment: function(c) {
		var me = this;
		this.prepare_comment(c);

		var $timeline_item = $(frappe.render_template("timeline_item", {data:c}))
			.appendTo(me.list)
			.on("click", ".close", function() {
				var name = $(this).parents(".timeline-item:first").attr("data-name");
				me.delete_comment(name);
				return false;
			});


		if(c.comment_type==="Email") {
			this.last_type = c.comment_type;
			this.add_reply_btn_event($timeline_item, c);
		}

	},

	add_reply_btn_event: function($timeline_item, c) {
		var me = this;
		$timeline_item.find(".reply-link").on("click", function() {
			var name = $(this).attr("data-name");
			var last_email = null;

			// find the email tor reply to
			me.get_comments().forEach(function(c) {
				if(c.name==name) {
					last_email = c;
					return false;
				}
			});

			// make the composer
			new frappe.views.CommunicationComposer({
				doc: me.frm.doc,
				txt: "",
				frm: me.frm,
				last_email: last_email
			});
		});
	},

	prepare_comment: function(c) {
		if((c.comment_type || "Comment") === "Comment" && frappe.model.can_delete("Comment")) {
			c["delete"] = '<a class="close" href="#">&times;</a>';
		} else {
			c["delete"] = "";
		}

		if(!c.comment_by) c.comment_by = this.frm.doc.owner;

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
				c.comment = c.comment.split("<!-- original-reply -->")[0];
				c.comment = frappe.utils.strip_original_content(c.comment);
				c.comment = frappe.utils.remove_script_and_style(c.comment);

				c.original_comment = c.comment;
				c.comment = frappe.utils.toggle_blockquote(c.comment);
			}

			if(!frappe.utils.is_html(c.comment)) {
				c.comment_html = frappe.markdown(__(c.comment));
			} else {
				c.comment_html = c.comment;
				c.comment_html = frappe.utils.strip_whitespace(c.comment_html);
			}
		}
	},
	set_icon_and_color: function(c) {
		c.icon = {
			"Email": "octicon octicon-mail",
			"Chat": "octicon octicon-comment-discussion",
			"Phone": "octicon octicon-device-mobile",
			"SMS": "octicon octicon-comment",
			"Created": "octicon octicon-plus",
			"Submitted": "octicon octicon-lock",
			"Cancelled": "octicon octicon-x",
			"Assigned": "octicon octicon-person",
			"Assignment Completed": "octicon octicon-check",
			"Comment": "octicon octicon-comment-discussion",
			"Workflow": "octicon octicon-git-branch",
			"Label": "octicon octicon-tag",
			"Attachment": "octicon octicon-cloud-upload",
			"Attachment Removed": "octicon octicon-trashcan",
			"Shared": "octicon octicon-eye",
			"Unshared": "octicon octicon-circle-slash"
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
					me.input.val("");

					frappe.utils.play_sound("click");

					var comment = r.message;
					var comments = me.get_comments();
					var comment_exists = false;
					for (var i=0, l=comments.length; i<l; i++) {
						if (comments[i].name==comment.name) {
							comment_exists = true;
							break;
						}
					}
					if (comment_exists) {
						return;
					}

					me.frm.get_docinfo().comments = comments.concat([r.message]);
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
					frappe.utils.play_sound("delete");

					me.frm.get_docinfo().comments =
						$.map(me.frm.get_docinfo().comments,
							function(v) {
								if(v.name==name) return null;
								else return v;
							}
						);
					me.refresh(true);
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
});
