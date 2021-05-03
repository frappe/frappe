// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import FormTimeline from "./form_timeline";
frappe.ui.form.Footer = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.make_comment_box();
		this.make_timeline();
		// render-complete
		$(this.frm.wrapper).on("render_complete", () => {
			this.refresh();
		});
	},
	make: function() {
		this.wrapper = $(frappe.render_template("form_footer", {}))
			.appendTo(this.parent);
		this.wrapper.find(".btn-save").click(() => {
			this.frm.save('Save', null, this);
		});
	},
	make_comment_box: function() {
		this.frm.comment_box = frappe.ui.form.make_control({
			parent: this.wrapper.find(".comment-box"),
			render_input: true,
			only_input: true,
			enable_mentions: true,
			df: {
				fieldtype: 'Comment',
				fieldname: 'comment'
			},
			on_submit: (comment) => {
				if (strip_html(comment).trim() != "") {
					this.frm.comment_box.disable();
					frappe.xcall("frappe.desk.form.utils.add_comment", {
						reference_doctype: this.frm.doctype,
						reference_name: this.frm.docname,
						content: comment,
						comment_email: frappe.session.user,
						comment_by: frappe.session.user_fullname
					}).then((comment) => {
						let comment_item = this.frm.timeline.get_comment_timeline_item(comment);
						this.frm.comment_box.set_value('');
						frappe.utils.play_sound("click");
						this.frm.timeline.add_timeline_item(comment_item);
						this.frm.sidebar.refresh_comments_count && this.frm.sidebar.refresh_comments_count();
					}).finally(() => {
						this.frm.comment_box.enable();
					});
				}
			}
		});
	},
	make_timeline() {
		this.frm.timeline = new FormTimeline({
			parent: this.wrapper.find(".timeline"),
			frm: this.frm
		});
	},
	refresh: function() {
		if (this.frm.doc.__islocal) {
			this.parent.addClass("hide");
		} else {
			this.parent.removeClass("hide");
			this.frm.timeline.refresh();
		}
	},
});
