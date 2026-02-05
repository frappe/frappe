import "./assign_to";
import "./attachments";
import "./share";
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
			can_write:
				frappe.model.can_write(this.frm.doctype, this.frm.docname) &&
				!this.frm.fields_dict[this.frm.meta.image_field]?.df.read_only,
			image_field: this.frm.meta.image_field ?? false,
		});

		this.sidebar = $('<div class="form-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.user_actions = this.sidebar.find(".user-actions");
		this.image_section = this.sidebar.find(".sidebar-image-section");
		this.image_wrapper = this.image_section.find(".sidebar-image-wrapper");
		this.make_assignments();
		this.make_attachments();
		this.make_shared();

		this.make_tags();

		this.setup_keyboard_shortcuts();
		this.show_auto_repeat_status();
		frappe.ui.form.setup_user_image_event(this.frm);
		this.setup_copy_event();
		this.make_like();
		this.setup_print();
		this.setup_editable_title();
		this.refresh();
	}

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

			this.frm.tags && this.frm.tags.refresh(this.frm.get_docinfo()?.tags);

			this.refresh_web_view_count();
			this.refresh_creation_modified();
			frappe.ui.form.set_user_image(this.frm);
		}
		this.refresh_like();
	}

	setup_copy_event() {
		$(this.sidebar)
			.find(".sidebar-meta-details .form-name-copy")
			.tooltip()
			.on("click", (e) => {
				frappe.utils.copy_to_clipboard($(e.currentTarget).attr("data-copy"));
			});
	}

	setup_editable_title() {
		// setup editable title
		let form_sidebar_text = $(this.sidebar).find(".form-stats-likes .form-title-text");
		this.toolbar.setup_editable_title(form_sidebar_text);
	}

	setup_print() {
		const print_settings = frappe.model.get_doc(":Print Settings", "Print Settings");
		const allow_print_for_draft = cint(print_settings.allow_print_for_draft);
		const allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled);

		if (
			!frappe.model.is_submittable(this.frm.doc.doctype) ||
			this.frm.doc.docstatus == 1 ||
			(allow_print_for_cancelled && this.frm.doc.docstatus == 2) ||
			(allow_print_for_draft && this.frm.doc.docstatus == 0)
		) {
			if (frappe.model.can_print(null, this.frm) && !this.frm.meta.issingle) {
				let print_icon = this.page.add_action_icon(
					"printer",
					() => {
						this.frm.print_doc();
					},
					"",
					__("Print")
				);
				print_icon.css("background-color", "transparent");
				print_icon.addClass("p-0");
				this.sidebar.find(".form-print").append(print_icon);
			}
		}
	}

	make_like() {
		this.like_wrapper = this.sidebar.find(".liked-by");
		this.like_icon = this.sidebar.find(".liked-by .like-icon");
		this.like_count = this.sidebar.find(".liked-by .like-count");
		frappe.ui.setup_like_popover(this.sidebar.find(".form-stats-likes"), ".like-icon");

		this.like_icon.on("click", () => {
			frappe.ui.toggle_like(this.like_wrapper, this.frm.doctype, this.frm.doc.name, () => {
				this.refresh_like();
			});
		});
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
		this.sidebar
			.find(".modified-by")
			.html(
				get_user_message(
					this.frm.doc.modified_by,
					__("Last Edited by You", null),
					__("Last Edited by {0}", [get_user_link(this.frm.doc.modified_by)])
				) +
					" <br> " +
					comment_when(this.frm.doc.modified)
			);
		this.sidebar
			.find(".created-by")
			.html(
				get_user_message(
					this.frm.doc.owner,
					__("Created By You", null),
					__("Created By {0}", [get_user_link(this.frm.doc.owner)])
				) +
					" <br> " +
					comment_when(this.frm.doc.creation)
			);
	}

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
					let el = me.sidebar.find(".auto-repeat-status");
					el.find("span").html(__("Repeats {0}", [__(res.message.frequency)]));
					el.closest(".sidebar-section").removeClass("hidden");
					el.show();
					el.on("click", function () {
						frappe.set_route("Form", "Auto Repeat", me.frm.doc.auto_repeat);
					});
				},
			});
		}
	}

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
				$('<div class="user-action-row"></div>').appendTo(
					this.user_actions.removeClass("hidden")
				)
			)
			.on("click", click);
	}

	clear_user_actions() {
		this.user_actions.addClass("hidden");
		this.user_actions.find(".user-action-row").remove();
	}

	refresh_image() {}

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
