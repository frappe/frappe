// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Comments = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper =this.parent;
		$('<div class="comment-connector"></div>').appendTo(this.parent);
		this.list = $('<div class="comments"></div>')
			.appendTo(this.parent);

		this.row = $(repl('<div class="media comment" data-name="%(name)s">\
			<span class="pull-left avatar avatar-small">\
				<img class="media-object" src="%(image)s">\
			</span>\
			<div class="media-body">\
				<textarea style="height: 80px" class="form-control"></textarea>\
				<div class="text-right" style="margin-top: 10px">\
					<button class="btn btn-default btn-go btn-sm">\
						<i class="icon-ok"></i> ' + __("Add comment") + '</button>\
				</div>\
			</div>\
		</div>', {image: frappe.user_info(user).image,
			fullname: user_fullname})).appendTo(this.parent);

		this.input = this.row.find(".form-control");
		this.button = this.row.find(".btn-go")
			.click(function() {
				me.add_comment(this);
			});
	},
	refresh: function() {
		var me = this;
		if(this.frm.doc.__islocal) {
			this.wrapper.toggle(false);
			return;
		}
		this.wrapper.toggle(true);
		this.list.empty();

		comments = [{"comment": __("Created"), "comment_type": "Created",
			"comment_by": this.frm.doc.owner, "creation": this.frm.doc.creation}].concat(this.get_comments());

		$.each(comments, function(i, c) {
			if((c.comment_type || "Comment") === "Comment" && frappe.model.can_delete("Comment")) {
				c["delete"] = '<a class="close" href="#">&times;</a>';
			} else {
				c["delete"] = "";
			}
			c.image = frappe.user_info(c.comment_by).image || frappe.get_gravatar(c.comment_by);
			c.comment_on = comment_when(c.creation);
			c.fullname = frappe.user_info(c.comment_by).fullname;

			if(!c.comment_type) c.comment_type = "Comment"

			c.icon = {
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

			c.icon_bg = {
				"Created": "#1abc9c",
				"Submitted": "#3498db",
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

			if(!c.icon_fg) c.icon_fg = "#fff";

			// label view
			if(c.comment_type==="Workflow" || c.comment_type==="Label") {
				c.comment_html = repl('<span class="label label-%(style)s">%(text)s</span>', {
					style: frappe.utils.guess_style(c.comment),
					text: __(c.comment)
				});
			} else {
				c.comment_html = frappe.markdown(__(c.comment));
			}

			// icon centering -- pixed perfect
			if(in_list(["Comment"], c.comment_type)) {
				c.padding = "padding-left: 8px;";
			} else {
				c.padding = "";
			}

			$(repl('<div class="media comment" data-name="%(name)s">\
					<span class="pull-left avatar avatar-small">\
						<img class="media-object" src="%(image)s">\
					</span>\
					<span class="pull-left comment-icon">\
						<i class="%(icon)s icon-timeline" \
							style="background-color: %(icon_bg)s; color: %(icon_fg)s; %(padding)s"></i>\
					</span>\
					<div class="media-body comment-body">\
						%(comment_html)s\
						<div>\
							<span class="small text-muted">\
								%(fullname)s / %(comment_on)s %(delete)s</span>\
						</div>\
					</div>\
				</div>', c))
				.appendTo(me.list)
				.on("click", ".close", function() {
					var name = $(this).parents(".comment:first").attr("data-name");
					me.delete_comment(name);
					return false;
				})

		});
	},
	get_comments: function() {
		return this.frm.get_docinfo().comments
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
			method: "frappe.widgets.form.utils.add_comment",
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
					me.refresh();
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
					me.refresh();
					me.frm.toolbar.show_infobar();
				}
			}
		});
	}
})
