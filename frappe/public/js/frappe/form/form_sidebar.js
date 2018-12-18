frappe.provide("frappe.ui.form");
frappe.ui.form.Sidebar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	},

	make: function() {
		var sidebar_content = frappe.render_template("form_sidebar", {doctype: this.frm.doctype, frm:this.frm});

		this.sidebar = $('<div class="form-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.ratings = this.sidebar.find(".sidebar-rating");
		this.comments = this.sidebar.find(".sidebar-comments");
		this.user_actions = this.sidebar.find(".user-actions");
		this.image_section = this.sidebar.find(".sidebar-image-section");
		this.image_wrapper = this.image_section.find('.sidebar-image-wrapper');

		this.make_assignments();
		this.make_attachments();
		this.make_shared();
		this.make_viewers();
		this.make_tags();
		this.make_like();

		this.bind_events();
		frappe.ui.form.setup_user_image_event(this.frm);

		this.refresh();

	},

	bind_events: function() {
		var me = this;

		// scroll to comments
		this.comments.on("click", function() {
			frappe.utils.scroll_to(me.frm.footer.wrapper.find(".form-comments"), true);
		});

		this.like_icon.on("click", function() {
			frappe.ui.toggle_like(me.like_icon, me.frm.doctype, me.frm.doc.name, function() {
				me.refresh_like();
			});
		})
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

			this.refresh_like();
			this.setup_ratings();
			frappe.ui.form.set_user_image(this.frm);
		}
	},

	refresh_comments: function() {
		$.map(this.frm.timeline.get_communications(), function(c) {
			return (c.communication_type==="Communication" || (c.communication_type=="Comment" && c.comment_type==="Comment")) ? c : null;
		});
		this.comments.find(".n-comments").html(this.frm.get_docinfo().total_comments);
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
			.appendTo(this.user_actions.removeClass("hidden"))).on("click", click);
	},
	clear_user_actions: function() {
		this.user_actions.addClass("hidden")
		this.user_actions.find(".user-action-row").remove();
	},

	make_like: function() {
		this.like_wrapper = this.sidebar.find(".liked-by");
		this.like_icon = this.sidebar.find(".liked-by .octicon-heart");
		this.like_count = this.sidebar.find(".liked-by .likes-count");
		frappe.ui.setup_like_popover(this.sidebar.find(".liked-by-parent"), ".liked-by");
	},

	refresh_like: function() {
		if (!this.like_icon) {
			return;
		}

		this.like_wrapper.attr("data-liked-by", this.frm.doc._liked_by);

		this.like_icon.toggleClass("text-extra-muted not-liked",
			!frappe.ui.is_liked(this.frm.doc))
			.attr("data-doctype", this.frm.doctype)
			.attr("data-name", this.frm.doc.name);

		this.like_count.text(JSON.parse(this.frm.doc._liked_by || "[]").length);
	},

	refresh_image: function() {
	},

	setup_ratings: function() {
		var _ratings = this.frm.get_docinfo().rating || 0;

		if(_ratings) {
			this.ratings.removeClass("hide");
			var rating_icons = frappe.render_template("rating_icons", {rating: _ratings, show_label: false});
			this.ratings.find(".rating-icons").html(rating_icons);
		}
	}
});
