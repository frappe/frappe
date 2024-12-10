import "./assign_to";
import "./attachments";
import "./share";
import "./review";
import "./document_follow";
import "./user_image";
import "./form_sidebar_users";
import { get_user_link, get_user_message } from "../footer/version_timeline_content_builder";

frappe.ui.form.Sidebar = class {
	constructor(opts) {
		$.extend(this, opts);
	}

	make() {
		var sidebar_content = frappe.render_template("form_sidebar", {
			doctype: this.frm.doctype,
			frm: this.frm,
			can_write: frappe.model.can_write(this.frm.doctype, this.frm.docname),
		});

		this.sidebar = $('<div class="form-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

<<<<<<< HEAD
		this.comments = this.sidebar.find(".form-sidebar-stats .comments");
=======
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		this.user_actions = this.sidebar.find(".user-actions");
		this.image_section = this.sidebar.find(".sidebar-image-section");
		this.image_wrapper = this.image_section.find(".sidebar-image-wrapper");
		this.make_assignments();
		this.make_attachments();
		this.make_review();
		this.make_shared();

		this.make_tags();
<<<<<<< HEAD
		this.make_like();
		this.make_follow();

		this.bind_events();
		this.setup_keyboard_shortcuts();
		this.show_auto_repeat_status();
=======

		this.setup_keyboard_shortcuts();
		this.show_auto_repeat_status();
		this.show_error_log_status();
		this.show_webhook_request_log_status();
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		frappe.ui.form.setup_user_image_event(this.frm);

		this.refresh();
	}

<<<<<<< HEAD
	bind_events() {
		var me = this;

		// scroll to comments
		this.comments.on("click", function () {
			frappe.utils.scroll_to(me.frm.footer.wrapper.find(".comment-box"), true);
		});

		this.like_icon.on("click", function () {
			frappe.ui.toggle_like(me.like_wrapper, me.frm.doctype, me.frm.doc.name, function () {
				me.refresh_like();
			});
		});
	}

=======
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	setup_keyboard_shortcuts() {
		// add assignment shortcut
		let assignment_link = this.sidebar.find(".add-assignment");
		frappe.ui.keys.get_shortcut_group(this.page).add(assignment_link);
	}

	refresh() {
		if (this.frm.doc.__islocal) {
			this.sidebar.toggle(false);
			this.page.sidebar.addClass("hide-sidebar");
		} else {
			this.page.sidebar.removeClass("hide-sidebar");
			this.sidebar.toggle(true);
			this.frm.assign_to.refresh();
			this.frm.attachments.refresh();
			this.frm.shared.refresh();

			this.frm.tags && this.frm.tags.refresh(this.frm.get_docinfo().tags);

<<<<<<< HEAD
			if (this.frm.doc.route && cint(frappe.boot.website_tracking_enabled)) {
				let route = this.frm.doc.route;
				frappe.utils.get_page_view_count(route).then((res) => {
					this.sidebar
						.find(".pageview-count")
						.html(__("{0} Web page views", [String(res.message).bold()]));
				});
			}

			this.sidebar
				.find(".modified-by")
				.html(
					get_user_message(
						this.frm.doc.modified_by,
						__("You last edited this", null),
						__("{0} last edited this", [get_user_link(this.frm.doc.modified_by)])
					) +
						" · " +
						comment_when(this.frm.doc.modified)
				);
			this.sidebar
				.find(".created-by")
				.html(
					get_user_message(
						this.frm.doc.owner,
						__("You created this", null),
						__("{0} created this", [get_user_link(this.frm.doc.owner)])
					) +
						" · " +
						comment_when(this.frm.doc.creation)
				);

			this.refresh_like();
			this.refresh_follow();
			this.refresh_comments_count();
=======
			this.refresh_web_view_count();
			this.refresh_creation_modified();
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			frappe.ui.form.set_user_image(this.frm);
		}
	}

<<<<<<< HEAD
=======
	refresh_web_view_count() {
		if (this.frm.doc.route && cint(frappe.boot.website_tracking_enabled)) {
			let route = this.frm.doc.route;
			frappe.utils.get_page_view_count(route).then((res) => {
				this.sidebar
					.find(".pageview-count")
					.removeClass("hidden")
					.html(__("{0} Web page views", [String(res.message).bold()]));
			});
		}
	}

	refresh_creation_modified() {
		let user_list = [this.frm.doc.owner, this.frm.doc.modified_by];
		if (this.frm.doc.owner === this.frm.doc.modified_by) {
			user_list = [this.frm.doc.owner];
		}

		let avatar_group = frappe.avatar_group(user_list, 5, {
			align: "left",
			overlap: true,
		});

		this.sidebar.find(".created-modified-section").append(avatar_group);

		let creation_message =
			get_user_message(
				this.frm.doc.owner,
				__("You created this", null),
				__("{0} created this", [get_user_link(this.frm.doc.owner)])
			) +
			" · " +
			comment_when(this.frm.doc.creation);

		let modified_message =
			get_user_message(
				this.frm.doc.modified_by,
				__("You last edited this", null),
				__("{0} last edited this", [get_user_link(this.frm.doc.modified_by)])
			) +
			" · " +
			comment_when(this.frm.doc.modified);

		if (user_list.length === 1) {
			// same user created and edited

			avatar_group.find(".avatar").popover({
				trigger: "hover",
				html: true,
				content: creation_message + "<br>" + modified_message,
			});
		} else {
			avatar_group.find(".avatar:first-child").popover({
				trigger: "hover",
				html: true,
				content: creation_message,
			});

			avatar_group.find(".avatar:last-child").popover({
				trigger: "hover",
				html: true,
				content: modified_message,
			});
		}
	}

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	show_auto_repeat_status() {
		if (this.frm.meta.allow_auto_repeat && this.frm.doc.auto_repeat) {
			const me = this;
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Auto Repeat",
					filters: {
						name: this.frm.doc.auto_repeat,
					},
					fieldname: ["frequency"],
				},
				callback: function (res) {
<<<<<<< HEAD
					me.sidebar
						.find(".auto-repeat-status")
						.html(__("Repeats {0}", [__(res.message.frequency)]));
					me.sidebar.find(".auto-repeat-status").on("click", function () {
=======
					let el = me.sidebar.find(".auto-repeat-status");
					el.find("span").html(__("Repeats {0}", [__(res.message.frequency)]));
					el.closest(".sidebar-section").removeClass("hidden");
					el.show();
					el.on("click", function () {
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
						frappe.set_route("Form", "Auto Repeat", me.frm.doc.auto_repeat);
					});
				},
			});
		}
	}

<<<<<<< HEAD
=======
	show_error_log_status() {
		const docinfo = this.frm.get_docinfo();
		if (docinfo.error_log_exists) {
			let el = this.sidebar.find(".error-log-status");
			el.closest(".sidebar-section").removeClass("hidden");
			el.show();
			el.on("click", () => {
				frappe.set_route("List", "Error Log", {
					reference_doctype: this.frm.doc.doctype,
					reference_name: this.frm.doc.name,
				});
			});
		}
	}

	show_webhook_request_log_status() {
		const docinfo = this.frm.get_docinfo();
		if (docinfo.webhook_request_log_exists) {
			let el = this.sidebar.find(".webhook-request-log-status");
			el.closest(".sidebar-section").removeClass("hidden");
			el.show();
			el.on("click", () => {
				frappe.set_route("List", "Webhook Request Log", {
					reference_doctype: this.frm.doc.doctype,
					reference_document: this.frm.doc.name,
				});
			});
		}
	}

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	make_tags() {
		if (this.frm.meta.issingle) {
			this.sidebar.find(".form-tags").toggle(false);
			return;
		}

		let tags_parent = this.sidebar.find(".form-tags");

		this.frm.tags = new frappe.ui.TagEditor({
			parent: tags_parent,
			add_button: tags_parent.find(".add-tags-btn"),
			frm: this.frm,
			on_change: function (user_tags) {
				this.frm.tags && this.frm.tags.refresh(user_tags);
			},
		});
	}

	make_attachments() {
		var me = this;
		this.frm.attachments = new frappe.ui.form.Attachments({
			parent: me.sidebar.find(".form-attachments"),
			frm: me.frm,
		});
	}

	make_assignments() {
		this.frm.assign_to = new frappe.ui.form.AssignTo({
			parent: this.sidebar.find(".form-assignments"),
			frm: this.frm,
		});
	}

	make_shared() {
		this.frm.shared = new frappe.ui.form.Share({
			frm: this.frm,
			parent: this.sidebar.find(".form-shared"),
		});
	}

	add_user_action(label, click) {
		return $("<a>")
			.html(label)
			.appendTo(
<<<<<<< HEAD
				$('<li class="user-action-row">').appendTo(this.user_actions.removeClass("hidden"))
=======
				$('<div class="user-action-row"></div>').appendTo(
					this.user_actions.removeClass("hidden")
				)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
			)
			.on("click", click);
	}

	clear_user_actions() {
		this.user_actions.addClass("hidden");
		this.user_actions.find(".user-action-row").remove();
	}

<<<<<<< HEAD
	make_like() {
		this.like_wrapper = this.sidebar.find(".liked-by");
		this.like_icon = this.sidebar.find(".liked-by .like-icon");
		this.like_count = this.sidebar.find(".liked-by .like-count");
		frappe.ui.setup_like_popover(this.sidebar.find(".form-stats-likes"), ".like-icon");
	}

	make_follow() {
		this.follow_button = this.sidebar.find(".form-sidebar-stats .form-follow");

		this.follow_button.on("click", () => {
			let is_followed = this.frm.get_docinfo().is_document_followed;
			frappe
				.call("frappe.desk.form.document_follow.update_follow", {
					doctype: this.frm.doctype,
					doc_name: this.frm.doc.name,
					following: !is_followed,
				})
				.then(() => {
					frappe.model.set_docinfo(
						this.frm.doctype,
						this.frm.doc.name,
						"is_document_followed",
						!is_followed
					);
					this.refresh_follow(!is_followed);
				});
		});
	}

	refresh_follow(follow) {
		if (follow == null) {
			follow = this.frm.get_docinfo().is_document_followed;
		}
		this.follow_button.text(follow ? __("Unfollow") : __("Follow"));
	}

	refresh_like() {
		if (!this.like_icon) {
			return;
		}

		this.like_wrapper.attr("data-liked-by", this.frm.doc._liked_by);
		const liked = frappe.ui.is_liked(this.frm.doc);
		this.like_wrapper
			.toggleClass("not-liked", !liked)
			.toggleClass("liked", liked)
			.attr("data-doctype", this.frm.doctype)
			.attr("data-name", this.frm.doc.name);

		this.like_count && this.like_count.text(JSON.parse(this.frm.doc._liked_by || "[]").length);
	}

	refresh_comments_count() {
		let count = (this.frm.get_docinfo().comments || []).length;
		this.comments.find(".comments-count").html(count);
	}

=======
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	refresh_image() {}

	make_review() {
		const review_wrapper = this.sidebar.find(".form-reviews");
		if (frappe.boot.energy_points_enabled && !this.frm.is_new()) {
			this.frm.reviews = new frappe.ui.form.Review({
				parent: review_wrapper,
				frm: this.frm,
			});
		} else {
			review_wrapper.remove();
		}
	}

	reload_docinfo(callback) {
		frappe.call({
			method: "frappe.desk.form.load.get_docinfo",
			args: {
				doctype: this.frm.doctype,
				name: this.frm.docname,
			},
			callback: (r) => {
				// docinfo will be synced
				if (callback) callback(r.docinfo);
				this.frm.timeline && this.frm.timeline.refresh();
				this.frm.assign_to.refresh();
				this.frm.attachments.refresh();
			},
		});
	}
};
