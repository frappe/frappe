

import './assign_to';
import './attachments';
import './share';
import './review';
import './document_follow';
import './user_image';
import './form_viewers';

frappe.ui.form.Sidebar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	},

	make: function() {
		var sidebar_content = frappe.render_template("form_sidebar", {doctype: this.frm.doctype, frm:this.frm});

		this.sidebar = $('<div class="form-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.comments = this.sidebar.find(".sidebar-comments");
		this.user_actions = this.sidebar.find(".user-actions");
		this.image_section = this.sidebar.find(".sidebar-image-section");
		this.image_wrapper = this.image_section.find('.sidebar-image-wrapper');
		this.make_assignments();
		this.make_attachments();
		this.make_review();
		this.make_shared();
		this.make_viewers();

		this.make_tags();
		this.make_like();
		if (frappe.boot.user.document_follow_notify) {
			this.make_follow();
		}

		this.bind_events();
		this.setup_keyboard_shortcuts();
		this.show_auto_repeat_status();
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
		});
	},

	setup_keyboard_shortcuts() {
		// add assignment shortcut
		let assignment_link = this.sidebar.find('.add-assignment');
		frappe.ui.keys
			.get_shortcut_group(this.page)
			.add(assignment_link);
	},

	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.sidebar.toggle(false);
		} else {
			this.sidebar.toggle(true);
			this.frm.assign_to.refresh();
			this.frm.attachments.refresh();
			this.frm.shared.refresh();
			if (frappe.boot.user.document_follow_notify) {
				this.frm.follow.refresh();
			}
			this.frm.viewers.refresh();
			this.frm.tags && this.frm.tags.refresh(this.frm.get_docinfo().tags);
			this.sidebar.find(".modified-by").html(__("{0} edited this {1}",
				["<strong>" + frappe.user.full_name(this.frm.doc.modified_by) + "</strong>",
					"<br>" + comment_when(this.frm.doc.modified)]));
			this.sidebar.find(".created-by").html(__("{0} created this {1}",
				["<strong>" + frappe.user.full_name(this.frm.doc.owner) + "</strong>",
					"<br>" + comment_when(this.frm.doc.creation)]));

			this.refresh_like();
			frappe.ui.form.set_user_image(this.frm);
		}
	},

	show_auto_repeat_status: function() {
		if (this.frm.meta.allow_auto_repeat && this.frm.doc.auto_repeat) {
			const me = this;
			frappe.call({
				method: "frappe.client.get_value",
				args:{
					doctype: "Auto Repeat",
					filters: {
						name: this.frm.doc.auto_repeat
					},
					fieldname: ["frequency"]
				},
				callback: function(res) {
					me.sidebar.find(".auto-repeat-status").html(__("Repeats {0}", [res.message.frequency]));
					me.sidebar.find(".auto-repeat-status").on("click", function(){
						frappe.set_route("Form", "Auto Repeat", me.frm.doc.auto_repeat);
					});
				}
			});
		}
	},

	refresh_comments: function() {
		$.map(this.frm.timeline.get_communications(), function(c) {
			return (c.communication_type==="Communication" || (c.communication_type=="Comment" && c.comment_type==="Comment")) ? c : null;
		});
		this.comments.find(".n-comments").html(this.frm.get_docinfo().total_comments);
	},

	make_tags: function() {
		if (this.frm.meta.issingle) {
			this.sidebar.find(".form-tags").toggle(false);
			return;
		}

		this.frm.tags = new frappe.ui.TagEditor({
			parent: this.sidebar.find(".tag-area"),
			frm: this.frm,
			on_change: function(user_tags) {
				this.frm.tags && this.frm.tags.refresh(user_tags);
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
	make_follow: function(){
		this.frm.follow = new frappe.ui.form.DocumentFollow({
			frm: this.frm,
			parent: this.sidebar.find(".followed-by-section")
		});
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

	make_review: function() {
		if (frappe.boot.energy_points_enabled && !this.frm.is_new()) {
			this.frm.reviews = new frappe.ui.form.Review({
				parent: this.sidebar.find(".form-reviews"),
				frm: this.frm
			});
		}
	},

	reload_docinfo: function(callback) {
		frappe.call({
			method: "frappe.desk.form.load.get_docinfo",
			args: {
				doctype: this.frm.doctype,
				name: this.frm.docname
			},
			callback: (r) => {
				// docinfo will be synced
				if(callback) callback(r.docinfo);
				this.frm.timeline && this.frm.timeline.refresh();
				this.frm.assign_to.refresh();
				this.frm.attachments.refresh();
			}
		});
	}

});
