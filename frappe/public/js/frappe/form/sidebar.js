frappe.provide("frappe.ui.form");
frappe.ui.form.Sidebar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},

	make: function() {
		var sidebar_content = frappe.render_template("form_sidebar", {doctype: this.frm.doctype, frm:this.frm});

		this.offcanvas_form_sidebar = $(".offcanvas .form-sidebar").html(sidebar_content);
		this.page_sidebar = $('<div class="form-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.sidebar = this.page_sidebar.add(this.offcanvas_form_sidebar);
		this.comments = this.sidebar.find(".sidebar-comments");
		this.user_actions = this.sidebar.find(".user-actions");

		this.make_assignments();
		this.make_attachments();
		this.make_shared();
		this.make_viewers();
		this.make_tags();

		this.bind_events();

		this.refresh();

	},

	bind_events: function() {
		var me = this;

		// scroll to comments
		this.comments.on("click", function() {
			$(".offcanvas").removeClass("active-left active-right");
			frappe.ui.scroll(me.frm.footer.wrapper.find(".form-comments"), true);
		});
	},

	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.sidebar.toggle(false);
		} else {
			this.sidebar.toggle(true);
			this.frm.assign_to.refresh();
			this.frm.attachments.refresh();
			this.frm.shared.refresh();
			this.frm.viewers.refresh();
			this.frm.tags && this.frm.tags.refresh(this.frm.doc._user_tags);
			this.sidebar.find(".modified-by").html(__("{0} edited this {1}",
				["<strong>" + frappe.user.full_name(this.frm.doc.modified_by) + "</strong>",
				"<br>" + comment_when(this.frm.doc.modified)]));
			this.sidebar.find(".created-by").html(__("{0} created this {1}",
				["<strong>" + frappe.user.full_name(this.frm.doc.owner) + "</strong>",
				"<br>" + comment_when(this.frm.doc.creation)]));
		}
	},

	refresh_comments: function() {
		var comments = $.map(this.frm.comments.get_comments(), function(c) {
			return (c.comment_type==="Email" || c.comment_type==="Comment") ? c : null;
		});
		this.comments.find(".n-comments").html(comments.length);
	},

	make_tags: function() {
		var me = this;
		if (this.frm.meta.issingle) {
			this.sidebar.find(".form-tags").toggle(false);
			return;
		}

		this.frm.tags = new frappe.ui.TagEditor({
			parent: this.sidebar.find(".tag-area"),
			frm: this.frm,
			on_change: function(user_tags) {
				me.frm.doc._user_tags = user_tags;
			}
		});
	},
	make_attachments: function() {
		var me = this;
		this.frm.attachments = new frappe.ui.form.Attachments({
			parent: me.sidebar.find(".form-attachments"),
			frm: me.frm
		});
	},
	make_assignments: function() {
		this.frm.assign_to = new frappe.ui.form.AssignTo({
			parent: this.sidebar.find(".form-assignments"),
			frm: this.frm
		});
	},
	make_shared: function() {
		this.frm.shared = new frappe.ui.form.Share({
			frm: this.frm,
			parent: this.sidebar.find(".form-shared")
		});
	},
	make_viewers: function() {
		this.frm.viewers = new frappe.ui.form.Viewers({
			frm: this.frm,
			parent: this.sidebar.find(".form-viewers")
		});
	},
	add_user_action: function(label, click) {
		return $('<a>').html(label).appendTo($('<li class="user-action-row">')
			.appendTo(this.user_actions.removeClass("hide"))).on("click", click);
	},
	clear_user_actions: function() {
		this.user_actions.addClass("hide")
		this.user_actions.find(".user-action-row").remove();
	},
});
