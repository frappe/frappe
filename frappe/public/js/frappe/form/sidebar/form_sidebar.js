import "./assign_to";
import "./attachments";
import "./share";
import "./user_image";
import "./form_sidebar_users";
import "./form_sidebar_connections";

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
		this.user_actions_list = this.sidebar.find(".user-actions-list");
		this.image_section = this.sidebar.find(".sidebar-image-section");
		this.image_wrapper = this.image_section.find(".sidebar-image-wrapper");
		this.make_assignments();
		this.make_attachments();
		this.make_shared();

		this.make_tags();
		this.make_connections();
		this.make_actions();

		this.setup_keyboard_shortcuts();
		this.show_auto_repeat_status();
		frappe.ui.form.setup_user_image_event(this.frm);
		this.setup_copy_event();
		this.make_like();
		this.setup_print();
		this.setup_editable_title();
		this.setup_activity_fade();
		this.refresh();
	}

	setup_activity_fade() {
		const $activity = this.sidebar.find(".form-sidebar-activity");
		// the column scrolls; the sidebar itself does when it is the small-screen overlay
		const scrollers = [this.page.sidebar[0], this.sidebar[0]].filter(Boolean);
		const update = () => {
			const behind = scrollers.some(
				(el) => el.scrollHeight - el.scrollTop - el.clientHeight > 1
			);
			$activity.toggleClass("has-content-behind", behind);
		};
		// the form makes a new sidebar on every render, in the same page column
		const previous = this.page.sidebar_fade;
		if (previous) {
			previous.observer.disconnect();
			previous.scrollers.forEach((el) => el.removeEventListener("scroll", previous.update));
		}
		scrollers.forEach((el) => el.addEventListener("scroll", update, { passive: true }));
		const observer = new ResizeObserver(update);
		scrollers.forEach((el) => observer.observe(el));
		this.page.sidebar_fade = { observer, scrollers, update };
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
			this.refresh_actions();
			frappe.ui.form.set_user_image(this.frm);
		}
		this.refresh_like();
	}

	make_actions() {
		this.$actions = this.sidebar.find(".form-sidebar-actions");
		this.$sections = this.sidebar.find(".form-sidebar-sections");
		this.actions = [
			{
				key: "assign",
				icon: "users",
				label: __("Assign"),
				section: ".form-assignments",
				// the server only asks for read access to assign
				allowed: () => true,
				has_items: (docinfo) => Boolean(docinfo.assignments?.length),
				click: () => this.frm.assign_to.add(),
			},
			{
				key: "attachments",
				icon: "paperclip",
				label: __("Add attachment"),
				section: ".form-attachments",
				add_button: ".add-attachment-btn",
				allowed: () => this.frm.has_perm("write"),
				has_items: () => Boolean(this.frm.attachments.get_attachments().length),
				click: () => this.frm.attachments.new_attachment(),
			},
			this.frm.tags && {
				key: "tags",
				icon: "tag",
				label: __("Add Tags"),
				section: ".form-tags",
				add_button: ".add-tags-btn",
				allowed: () => this.frm.has_perm("write"),
				has_items: () => Boolean(this.frm.tags.tags?.tagsList.length),
				picker: true,
			},
			{
				key: "share",
				icon: "share-2",
				label: __("Share"),
				section: ".form-shared",
				add_button: ".share-doc-btn",
				allowed: () => frappe.model.can_share(this.frm.doctype, this.frm),
				has_items: (docinfo) =>
					(this.frm.shared.shared || docinfo.shared || []).some(
						(s) => s && (s.user || s.everyone)
					),
				click: () => this.frm.share_doc(),
			},
		].filter(Boolean);

		for (const action of this.actions) {
			action.$button = frappe.ui
				.button({
					icon: action.icon,
					variant: "ghost",
					tooltip: action.label,
					css_class: "form-sidebar-action",
					attrs: { "data-action": action.key },
					onclick: action.click,
				})
				.appendTo(this.$actions);
			if (action.picker) this.frm.tags?.tags?.make_picker(action.$button);
		}

		$(this.frm.wrapper)
			.off("attachments_change.form_sidebar")
			.on("attachments_change.form_sidebar", () => this.refresh_actions());
	}

	refresh_actions() {
		if (!this.actions) return;
		const docinfo = this.frm.get_docinfo() || {};
		let any = false;
		for (const action of this.actions) {
			const has_items = action.has_items(docinfo);
			const allowed = action.allowed();
			this.sidebar.find(action.section).toggleClass("hidden", !has_items);
			action.$button.toggleClass("hidden", !allowed).prop("disabled", has_items);
			if (action.add_button) {
				this.sidebar
					.find(`${action.section} ${action.add_button}`)
					.toggleClass("hidden", !allowed);
			}
			any ||= has_items;
		}
		// removing a tag needs write access too
		this.sidebar.find(".form-tags").toggleClass("read-only", !this.frm.has_perm("write"));
		const can_act = this.actions.some((action) => action.allowed());
		this.$actions.toggleClass("hidden", !can_act);
		// the divider sits above Connections, so only when it is shown
		const has_connections = !this.sidebar.find(".form-connections").hasClass("hidden");
		this.$sections.toggleClass("hidden", !any).toggleClass("border-bottom", has_connections);
		this.$actions.toggleClass("border-bottom", !any && has_connections);
		this.sidebar
			.find(".form-attachments .form-sidebar-section-count")
			.text(this.frm.attachments.get_attachments().length || "");
	}

	get_user_tags() {
		return cstr(this.frm.doc._user_tags).split(",").filter(Boolean);
	}

	setup_copy_event() {
		let classes = [".form-name-copy", ".form-title-text"];

		$(this.sidebar)
			.find(".sidebar-meta-details " + classes.join(", "))
			.tooltip()
			.on("click", (e) => {
				frappe.utils.copy_to_clipboard($(e.currentTarget).attr("data-copy"));
			});
	}

	setup_editable_title() {
		let form_sidebar_text = $(this.sidebar).find(".form-stats-likes .form-title-edit");
		this.toolbar.setup_editable_title(form_sidebar_text);
	}

	setup_print() {
		if (frappe.model.can_print_doc(this.frm)) {
			frappe.ui
				.button({
					icon: "printer",
					variant: "ghost",
					tooltip: __("Print"),
					onclick: () => this.frm.print_doc(),
				})
				.appendTo(this.sidebar.find(".form-print"));
		}
	}

	make_like() {
		this.like_wrapper = this.sidebar.find(".liked-by");
		this.like_icon = this.sidebar.find(".liked-by .like-icon");
		frappe.ui.setup_like_popover(this.sidebar.find(".form-stats-likes"), ".like-icon");

		this.like_wrapper.on("click", () => {
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
		const absolute =
			cint(frappe.boot.user.show_absolute_datetime_in_timeline) ||
			frappe.defaults.is_enabled("show_absolute_datetime_in_timeline");
		const when = (datetime) =>
			absolute ? frappe.datetime.str_to_user(datetime) : comment_when(datetime);
		const row = (user, message) =>
			$(`<div class="form-sidebar-activity-user">
				<div class="form-sidebar-activity-name ellipsis text-ink-gray-8" tabindex="0"></div>
				<div class="text-ink-gray-5">${message}</div>
			</div>`)
				.find(".form-sidebar-activity-name")
				.text(frappe.user.full_name(user))
				.attr("data-user", user)
				.end();

		// cards from the last render would outlive their names
		(this.activity_cards || []).forEach((card) => card.destroy());
		const $users = this.sidebar
			.find(".form-sidebar-activity-users")
			.empty()
			.append(
				row(this.frm.doc.modified_by, __("Edited {0}", [when(this.frm.doc.modified)])),
				row(this.frm.doc.owner, __("Created {0}", [when(this.frm.doc.creation)]))
			);
		this.activity_cards = $users
			.find(".form-sidebar-activity-name")
			.toArray()
			.map(
				(name) =>
					new frappe.ui.HoverCard(name, {
						side: "top",
						align: "start",
						css_class: "form-sidebar-user-card",
						content: () => this.get_user_card(name.dataset.user),
					})
			);

		if (this.frm.timeline) {
			frappe.ui
				.button({
					label: __("View activity"),
					variant: "outline",
					css_class: "form-sidebar-view-activity",
					onclick: () =>
						this.frm.timeline.timeline_wrapper[0]?.scrollIntoView({
							behavior: "smooth",
						}),
				})
				.appendTo($users);
		}
	}

	get_user_card(user) {
		const info = frappe.user_info(user);
		// fits the hover card's fixed width; a long email truncates, with the full one on hover
		const $card = $(`<div class="flex items-center gap-2 min-w-0">
			<div class="shrink-0">${frappe.avatar(user, "avatar-medium")}</div>
			<div class="flex flex-col min-w-0">
				<div class="text-base-medium text-ink-gray-8 ellipsis"></div>
				<div class="text-sm text-ink-gray-5 ellipsis"></div>
			</div>
		</div>`);
		$card.find(".text-base-medium").text(info.fullname || user);
		$card
			.find(".text-sm")
			.text(info.email || "")
			.attr("title", info.email || "");
		return $card[0];
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
			picker: true,
			on_change: (user_tags) => {
				this.frm.tags && this.frm.tags.refresh(user_tags);
				this.refresh_actions();
			},
		});
	}

	make_connections() {
		this.connections = new frappe.ui.form.SidebarConnections({
			frm: this.frm,
			wrapper: this.sidebar.find(".form-connections"),
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
		const parent = this.user_actions_list.length ? this.user_actions_list : this.user_actions;
		this.user_actions.removeClass("hidden");
		const row = $('<div class="user-action-row"></div>').appendTo(parent);

		return $('<a class="user-action-link"></a>')
			.html(
				`<span class="user-action-label">${label}</span>
				<span class="user-action-external-icon">${frappe.utils.icon("external-link", "sm")}</span>`
			)
			.appendTo(row)
			.on("click", click);
	}

	clear_user_actions() {
		this.user_actions.addClass("hidden");
		const parent = this.user_actions_list.length ? this.user_actions_list : this.user_actions;
		parent.find(".user-action-row").remove();
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
