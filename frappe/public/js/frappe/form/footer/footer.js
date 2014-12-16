// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Footer = Class.extend({
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
		this.make();
		this.make_assignments();
		this.make_attachments();
		this.make_tags();
		this.make_comments();
		// render-complete
		$(this.frm.wrapper).on("render_complete", function() {
			me.refresh();
		})
	},
	make: function() {
		var me = this;
		this.wrapper = $(frappe.render(frappe.templates.form_footer, {}))
			.appendTo(this.parent);
		this.wrapper.find(".btn-save").click(function() {
			me.frm.save('Save', null, this);
		})

	},
	make_tags: function() {
		if (this.frm.meta.issingle) {
			this.frm.sidebar.parent.find(".form-tags").toggle(false);
			return;
		}

		this.frm.tags = new frappe.ui.TagEditor({
			parent: this.frm.sidebar.parent.find(".tag-area"),
			frm: this.frm,
		})
	},
	make_attachments: function() {
		this.frm.attachments = new frappe.ui.form.Attachments({
			parent: this.frm.sidebar.parent.find(".form-attachments"),
			frm: this.frm
		});
	},
	make_assignments: function() {
		this.frm.assign_to = new frappe.ui.form.AssignTo({
			parent: this.frm.sidebar.parent.find(".form-assignments"),
			frm: this.frm
		});
	},
	make_comments: function() {
		this.frm.comments = new frappe.ui.form.Comments({
			parent: this.wrapper.find(".form-comments"),
			frm: this.frm
		})
	},
	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.parent.addClass("hide");
		} else {
			this.parent.removeClass("hide");
			this.frm.attachments.refresh();
			this.frm.comments.refresh();
			this.frm.assign_to.refresh();
			this.frm.tags && this.frm.tags.refresh();
		}
	},
});
