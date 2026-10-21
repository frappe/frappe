// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import BaseTimeline from "./base_timeline";
import {
	get_version_timeline_content,
	get_user_link,
	get_user_message,
} from "./version_timeline_content_builder";

function get_scroll_parent(el) {
	for (let node = el.parentElement; node; node = node.parentElement) {
		const overflow = getComputedStyle(node).overflowY;
		if (/(auto|scroll)/.test(overflow) && node.scrollHeight > node.clientHeight) {
			return node;
		}
	}
	return document.scrollingElement;
}

const MESSAGE_CLAMP_HEIGHT = 500;
class FormTimeline extends BaseTimeline {
	make() {
		super.make();
		this.setup_timeline_actions();
		this.render_timeline_items();
		this.setup_activity_title();
		this.setup_add_menu();
		this.setup_activity_filters();
		this.setup_comment_box();
		this.setup_field_changes_toggle();
		this.setup_value_tooltips();
		this.setup_file_lists();
		frappe.router.on("change", () => this.flush_comment_deletes());
		window.addEventListener("pagehide", () => this.send_pending_deletes());
	}

	refresh() {
		const same_doc = this.rendered_docname === this.frm.docname;
		if (same_doc && this.active_comment_edit?.is_open()) {
			this.refresh_pending = true;
			return;
		}
		this.refresh_pending = false;
		if (!same_doc && this.active_filter !== "all") {
			this.activity_tabs.set_value("all");
		}
		super.refresh();
		this.frm.trigger("timeline_refresh");
		this.setup_document_email_link();
	}

	setup_timeline_actions() {
		this.add_menu_items = [];
		if (this.frm.comment_box) {
			this.add_menu_items.push({
				label: __("Comment"),
				icon: "message-circle",
				action: () => this.toggle_comment_box(true),
				// apps that hide the comment box (ERPNext's CRM forms) hide this too
				condition: () => this.comment_box_wrapper?.[0]?.style.display !== "none",
			});
		}
		if (frappe.model.can_email(null, this.frm)) {
			this.add_menu_items.push({
				label: __("Email"),
				icon: "mail",
				action: () => this.compose_mail(),
			});
		}
		this.setup_new_event_button();
	}

	setup_new_event_button() {
		if (this.frm.meta.allow_events_in_timeline) {
			let create_event = () => {
				const args = {
					doc: this.frm.doc,
					frm: this.frm,
					recipients: this.get_recipient(),
					txt: frappe.markdown(this.frm.comment_box.get_value()),
				};
				return new frappe.views.InteractionComposer(args);
			};
			// the old New Event button stays (never shown) so apps that hide it,
			// like ERPNext's CRM forms, hide the menu item too
			const legacy_button = this.add_action_button(__("New Event"), create_event).attr(
				"hidden",
				true
			);
			this.timeline_actions_wrapper.hide();
			this.add_menu_items.push({
				label: __("Event"),
				icon: "calendar",
				action: create_event,
				condition: () => legacy_button[0].style.display !== "none",
			});
		}
	}

	setup_add_menu() {
		if (!this.add_menu_items.length) return;
		this.add_menu = new frappe.ui.Dropdown({
			button: {
				label: __("Add"),
				icon_left: "plus",
				icon_right: "chevron-down",
				css_class: "timeline-add-menu",
			},
			align: "end",
			options: () =>
				this.add_menu_items.map(({ label, icon, action, condition }) => ({
					label,
					icon,
					onclick: action,
					condition,
				})),
		});
		this.timeline_wrapper.find(".activity-title").append(this.add_menu.$trigger);
	}

	setup_comment_box() {
		this.comment_box_wrapper = this.frm.comment_box && $(this.frm.comment_box.parent);
		if (!this.comment_box_wrapper?.length) return;

		this.comment_box_wrapper.addClass("timeline-comment-box");
		this.activity_filters_wrapper.after(this.comment_box_wrapper);
		this.toggle_comment_box(false);

		const send = frappe.ui.button({
			icon: "send",
			variant: "ghost",
			tooltip: __("Send"),
			css_class: "timeline-comment-send",
			disabled: true,
			onclick: () => this.frm.comment_box.submit(),
		});
		this.comment_box_wrapper.find(".comment-input-container .frappe-control").append(send);
		this.frm.comment_box.quill?.on("text-change", () =>
			send.prop("disabled", !this.has_comment_draft())
		);

		this.comment_box_wrapper.on("focusout", () => {
			// wait for focus to settle, e.g. inside the mention list
			setTimeout(() => {
				const has_focus = this.comment_box_wrapper[0].contains(document.activeElement);
				if (!has_focus && !this.has_comment_draft()) {
					this.toggle_comment_box(false);
				}
			}, 200);
		});
	}

	has_comment_draft() {
		const value = this.frm.comment_box.get_value() || "";
		return Boolean(strip_html(value).trim() || value.includes("<img"));
	}

	toggle_comment_box(show) {
		if (!this.comment_box_wrapper) return;
		this.comment_box_wrapper.toggleClass("timeline-comment-box-open", show);
		if (show) {
			// after the menu that opened it hands focus back to its trigger;
			// the header is sticky, so the box may be far above the viewport;
			// it only scrolls when the box is out of sight
			setTimeout(() => {
				const box = this.comment_box_wrapper[0].getBoundingClientRect();
				const header = this.timeline_wrapper.find(".activity-title")[0];
				const visible_from = header ? header.getBoundingClientRect().bottom : 0;
				if (box.top < visible_from || box.bottom > window.innerHeight) {
					this.comment_box_wrapper[0].scrollIntoView({ block: "center" });
				}
				this.frm.comment_box.quill?.focus({ preventScroll: true });
			});
		}
	}

	setup_activity_title() {
		this.timeline_wrapper.remove(this.timeline_actions_wrapper);
		this.timeline_wrapper.find(".timeline-item.activity-title").remove();
		this.timeline_wrapper.prepend(`
				<div class="timeline-item activity-title">
				<h4>${__("Activity")}</h4>
				</div>
			`);
		this.timeline_wrapper
			.find(".timeline-item.activity-title")
			.append(this.timeline_actions_wrapper);
	}

	get_activity_filters() {
		return [
			{ category: "all", label: __("All", null, "Form timeline") },
			{ category: "changes", label: __("Changes", null, "Form timeline") },
			{ category: "attachments", label: __("Attachments", null, "Form timeline") },
			{ category: "comments", label: __("Comments", null, "Form timeline") },
			{ category: "emails", label: __("Emails", null, "Form timeline") },
		];
	}

	setup_activity_filters() {
		this.active_filter = "all";
		this.activity_tabs = new frappe.ui.TabButtons({
			label: __("Show activity", null, "Form timeline"),
			options: this.get_activity_filters().map(({ category, label }) => ({
				label,
				value: category,
			})),
			value: "all",
			on_change: (category) => {
				const pinned = this.is_header_pinned();
				this.active_filter = category;
				this.apply_activity_filters();
				if (pinned) this.timeline_wrapper[0].scrollIntoView({ block: "start" });
			},
		});
		this.activity_filters_wrapper = $(`<div class="timeline-filters"></div>`).append(
			this.activity_tabs.$el
		);
		this.timeline_wrapper.find(".activity-title").after(this.activity_filters_wrapper);
		this.apply_activity_filters();
	}

	is_header_pinned() {
		const header = this.timeline_wrapper.find(".activity-title")[0];
		if (!header) return false;
		const sticky_top = parseFloat(getComputedStyle(header).top);
		return (
			header.getBoundingClientRect().top <= sticky_top + 1 &&
			this.timeline_wrapper[0].getBoundingClientRect().top < sticky_top
		);
	}

	keep_scroll_position(update) {
		const header = this.timeline_wrapper.find(".activity-title")[0];
		const pinned = this.is_header_pinned();
		const anchors = this.get_scroll_anchors(header);

		const list = this.timeline_items_wrapper;
		list.css("min-height", list.outerHeight());
		update();
		list.css("min-height", "");

		for (const anchor of anchors) {
			const el = this.find_timeline_item(anchor.doctype, anchor.name);
			if (el) {
				const moved = el.getBoundingClientRect().top - anchor.top;
				if (moved) get_scroll_parent(el).scrollTop += moved;
				return;
			}
		}
		if (pinned) {
			this.timeline_wrapper[0].scrollIntoView({ block: "start" });
		}
	}

	get_scroll_anchors(header) {
		const visible_from = header ? header.getBoundingClientRect().bottom : 0;
		const anchors = this.timeline_items_wrapper
			.children(".timeline-item[data-name]:not(.timeline-item-filtered)")
			.toArray()
			.filter((el) => {
				const rect = el.getBoundingClientRect();
				return rect.bottom > visible_from && rect.top < window.innerHeight;
			})
			.map((el) => ({
				doctype: el.dataset.doctype,
				name: el.dataset.name,
				top: el.getBoundingClientRect().top,
			}));
		const highlight = this.get_pending_highlight();
		const edited = highlight && anchors.find((a) => a.name === highlight.name);
		return edited ? [edited, ...anchors] : anchors;
	}

	find_timeline_item(doctype, name) {
		return this.timeline_items_wrapper
			.children(".timeline-item:not(.timeline-item-filtered)")
			.toArray()
			.find((el) => el.dataset.doctype === doctype && el.dataset.name === name);
	}

	highlight_timeline_item(doctype, name) {
		this.pending_highlight = { doctype, name, until: Date.now() + 5000 };
		this.flash_timeline_item(doctype, name);
	}

	get_pending_highlight() {
		const highlight = this.pending_highlight;
		return highlight && highlight.until > Date.now() ? highlight : null;
	}

	flash_timeline_item(doctype, name) {
		const el = this.find_timeline_item(doctype, name);
		if (!el) return;
		el.classList.remove("timeline-item-highlight");
		void el.offsetWidth; // restart the animation
		el.classList.add("timeline-item-highlight");
	}

	apply_activity_filters() {
		this.timeline_items_wrapper.children(".timeline-item").each((i, el) => {
			$(el).toggleClass(
				"timeline-item-filtered",
				!this.matches_activity_filters(el.dataset.category)
			);
		});
		this.update_filter_empty_state();
		this.all_changes_link?.toggle(this.active_filter === "changes");
		this.fit_file_lists();
		this.clamp_long_messages();
	}

	clamp_long_messages() {
		this.timeline_items_wrapper
			.find(".timeline-message-box .content:not([data-clamp-checked])")
			.each((i, content) => {
				if (!content.offsetParent) return;
				content.dataset.clampChecked = "1";
				const check = () => {
					if (content.nextElementSibling?.classList.contains("timeline-message-more")) {
						return;
					}
					if (content.scrollHeight <= MESSAGE_CLAMP_HEIGHT + 100) return;
					content.classList.add("timeline-content-clamped");
					$(content).after(this.get_message_more_button(content));
				};
				check();
				$(content).find("img").one("load", check);
			});
	}

	get_message_more_button(content) {
		const button = frappe.ui.button({
			label: __("Show more"),
			icon_right: "chevron-down",
			css_class: "timeline-message-more",
			onclick: () => {
				const top = button[0].getBoundingClientRect().top;
				const clamped = content.classList.toggle("timeline-content-clamped");
				button.find(".es-button__label").text(clamped ? __("Show more") : __("Show less"));
				button.attr("aria-expanded", !clamped);
				if (clamped) {
					const moved = button[0].getBoundingClientRect().top - top;
					if (moved) get_scroll_parent(button[0]).scrollTop += moved;
				}
			},
			attrs: { "aria-expanded": "false" },
		});
		return button;
	}

	update_filter_empty_state() {
		this.filter_empty_state?.remove();
		this.filter_empty_state = null;
		if (!this.active_filter || this.active_filter === "all") return;
		const visible = this.timeline_items_wrapper.children(
			".timeline-item:not(.timeline-item-filtered):not(.timeline-item-deleted)"
		).length;
		if (visible) return;
		const title = {
			changes: __("No changes yet", null, "Form timeline"),
			attachments: __("No attachments yet", null, "Form timeline"),
			comments: __("No comments yet", null, "Form timeline"),
			emails: __("No emails yet", null, "Form timeline"),
		}[this.active_filter];
		this.filter_empty_state = frappe.ui
			.empty_state({
				icon: "inbox",
				title,
				actions: [{ label: __("Show all"), onclick: () => this.clear_activity_filters() }],
				css_class: "timeline-empty-state",
			})
			.insertAfter(this.timeline_items_wrapper);
	}

	clear_activity_filters() {
		this.activity_tabs.set_value("all");
	}

	matches_activity_filters(category) {
		return (
			!this.active_filter || this.active_filter === "all" || this.active_filter === category
		);
	}

	get_timeline_item(item) {
		const timeline_item = super.get_timeline_item(item);
		if (item.category) {
			timeline_item.attr("data-category", item.category);
		}
		if (!this.matches_activity_filters(item.category)) {
			timeline_item.addClass("timeline-item-filtered");
		}
		return timeline_item;
	}

	setup_value_tooltips() {
		frappe.ui.Tooltip?.delegate(
			this.timeline_wrapper,
			".timeline-change-old, .timeline-change-new, .timeline-row-value",
			{ only_on_overflow: true }
		);
	}

	setup_field_changes_toggle() {
		this.timeline_wrapper.on("click", ".timeline-changes-toggle", (e) => {
			const toggle = $(e.currentTarget);
			const expanded = toggle.attr("aria-expanded") !== "true";
			toggle.attr("aria-expanded", expanded);
			toggle.find(".es-button__label").text(expanded ? __("Hide") : __("Show"));
			toggle.siblings(".timeline-changes").prop("hidden", !expanded);
		});
		this.timeline_wrapper.on("click", ".timeline-changes-more-toggle", (e) => {
			const toggle = $(e.currentTarget);
			const expanded = toggle.attr("aria-expanded") !== "true";
			toggle.attr("aria-expanded", expanded);
			toggle
				.find(".es-button__label")
				.text(toggle.attr(expanded ? "data-hide-label" : "data-show-label"));
			toggle.closest(".timeline-changes").toggleClass("show-all", expanded);
		});
		frappe.ui.Tooltip?.delegate(this.timeline_wrapper, ".timeline-version-link", {
			text: __("Open version", null, "Form timeline"),
		});
	}

	group_timeline_items(items) {
		const grouped = [];
		for (const item of items) {
			const last = grouped[grouped.length - 1];
			const members = last?.members || [last];
			const same_day =
				last &&
				Math.abs(
					moment(members[members.length - 1].creation).diff(
						moment(item.creation),
						"hours"
					)
				) < 24;
			if (item.group && last && last.group === item.group && same_day) {
				last.members = last.members || [last];
				last.members.push(item);
			} else {
				grouped.push(item.group ? { ...item } : item);
			}
		}
		return grouped.map((item) => {
			if (!item.members) return item;
			return item.file_chip
				? this.get_attachment_group_item(item)
				: this.get_grouped_item(item);
		});
	}

	get_group_timestamp(members) {
		const at = (member) => moment(frappe.datetime.convert_to_user_tz(member.creation));
		const newest = at(members[0]);
		const oldest = at(members[members.length - 1]);
		const span = newest.isSame(oldest, "minute")
			? newest.format("lll")
			: `${oldest.format("lll")} – ${newest.format(
					newest.isSame(oldest, "day") ? "LT" : "lll"
			  )}`;
		return `<div class="timeline-timestamp timeline-group-range" title="${span}">${this.get_timestamp_text(
			members[0].creation
		)}</div>`;
	}

	get_attachment_group_item(group) {
		const { members, user } = group;
		const count = frappe.utils.bold(__("{0} files", [members.length], "Form timeline"));
		const user_link = get_user_link(user);
		const summary = group.is_file_upload
			? get_user_message(
					user,
					__("You attached {0}", [count], "Form timeline"),
					__("{0} attached {1}", [user_link, count], "Form timeline")
			  )
			: get_user_message(
					user,
					__("You removed {0}", [count], "Form timeline"),
					__("{0} removed {1}", [user_link, count], "Form timeline")
			  );
		return {
			...group,
			hide_timestamp: true,
			content: `${summary}
				<div class="timeline-file-list">
					${members.map((member) => member.file_chip).join("")}
					<button type="button" class="timeline-file-more" aria-expanded="false"></button>
				</div>
				${this.get_group_timestamp(members)}`,
		};
	}

	setup_file_lists() {
		this.timeline_wrapper.on("click", ".timeline-file-more", (e) => {
			const list = $(e.currentTarget).closest(".timeline-file-list").toggleClass("expanded");
			e.currentTarget.setAttribute("aria-expanded", list.hasClass("expanded"));
			this.fit_file_lists();
		});
		if (window.ResizeObserver) {
			let frame;
			new ResizeObserver(() => {
				cancelAnimationFrame(frame);
				frame = requestAnimationFrame(() => {
					this.fit_file_lists();
					// a timeline in a hidden tab (ERPNext's CRM forms) is measured once shown
					this.clamp_long_messages();
				});
			}).observe(this.timeline_items_wrapper[0]);
		}
	}

	fit_file_lists() {
		this.timeline_items_wrapper.find(".timeline-file-list").each((i, list) => {
			const chips = [...list.querySelectorAll(":scope > .timeline-file")];
			const more = list.querySelector(":scope > .timeline-file-more");
			chips.forEach((chip) => (chip.style.display = ""));
			if (list.classList.contains("expanded")) {
				more.textContent = __("Show less");
				more.style.display = "";
				return;
			}
			more.style.display = "none";
			// not displayed: nothing to measure yet
			if (!list.offsetParent || list.scrollWidth <= list.clientWidth) return;

			more.style.display = "";
			let hidden = 0;
			for (let n = chips.length - 1; n > 0 && list.scrollWidth > list.clientWidth; n--) {
				chips[n].style.display = "none";
				hidden++;
				more.textContent = __("+{0} more", [hidden]);
			}
		});
	}

	get_grouped_item(group) {
		const members = group.members;
		const users = [...new Set(members.map((member) => member.user))];
		const everyone = users.map((user) => {
			const own = members.filter((member) => member.user === user);
			const times = own.length > 1 ? __("{0} times", [own.length], "Form timeline") : "";
			const when = strip_html(this.get_timestamp_text(own[0].creation));
			return { user, meta: [times, when].filter(Boolean).join(" · ") };
		});
		const named = users.length === 3 ? 3 : 2;
		const names = this.get_names_with_others(
			users.slice(0, named),
			users.length - named,
			everyone
		);

		const repeats = users.length === 1 && members.length > 1 ? members.length : 0;
		let summary;
		if (group.group === "likes") {
			summary = get_user_message(
				users.length === 1 && users[0],
				__("You Liked"),
				__("{0} Liked", [names])
			);
		} else if (repeats) {
			summary = get_user_message(
				users[0],
				__("You viewed this {0} times", [repeats], "Form timeline"),
				__("{0} viewed this {1} times", [names, repeats], "Form timeline")
			);
		} else {
			summary = get_user_message(
				users.length === 1 && users[0],
				__("You viewed this"),
				__("{0} viewed this", [names])
			);
		}

		return {
			...group,
			hide_timestamp: true,
			content: `${summary}
				${this.get_group_timestamp(members)}`,
		};
	}

	get_names_with_others(users, others_count, everyone) {
		const names = users.map((user) =>
			frappe.utils.is_current_user(user)
				? `<span class="timeline-you">${__("You")}</span>`
				: get_user_link(user)
		);
		if (others_count > 0) {
			names.push(this.get_others_trigger(others_count, everyone));
		}
		return frappe.utils.comma_and(names);
	}

	get_others_trigger(count, entries) {
		const data = frappe.utils.escape_html(JSON.stringify(entries));
		return `<button type="button" class="timeline-others" data-others="${data}">${__(
			"{0} others",
			[count],
			"Form timeline"
		)}</button>`;
	}

	setup_others_cards() {
		this.timeline_items_wrapper.find(".timeline-others").each((i, el) => {
			if ($(el).data("es-hover-card")) return;
			frappe.ui.hover_card(el, {
				content: () => this.get_others_list(JSON.parse(el.dataset.others)),
				side: "bottom",
				align: "start",
				open_delay: 300,
				css_class: "timeline-others-card",
			});
			$(el).on("click", () => $(el).data("es-hover-card").open());
		});
	}

	get_others_list(entries) {
		const list = $(`<div class="timeline-others-list"></div>`);
		entries.forEach(({ user, meta }) => {
			const name = frappe.utils.is_current_user(user)
				? __("You")
				: frappe.user_info(user).fullname || user;
			list.append(`<div class="timeline-others-row">
				${frappe.avatar(user, "avatar-xs")}
				<span class="timeline-others-name">${frappe.utils.escape_html(name)}</span>
				${meta ? `<span class="timeline-others-meta">${frappe.utils.escape_html(meta)}</span>` : ""}
			</div>`);
		});
		return list[0];
	}

	setup_document_email_link() {
		let doc_info = this.doc_info || this.frm.get_docinfo();

		this.document_email_link_wrapper && this.document_email_link_wrapper.remove();

		if (doc_info.document_email) {
			const link = `<a class="document-email-link">${doc_info.document_email}</a>`;
			const message = __("Add to this activity by mailing to {0}", [link.bold()]);

			this.document_email_link_wrapper = $(`
				<div class="timeline-item">
					<div class="timeline-dot"></div>
					<div class="timeline-content">
						<span>${message}</span>
					</div>
				</div>
			`);
			this.timeline_items_wrapper.before(this.document_email_link_wrapper);

			this.document_email_link_wrapper.find(".document-email-link").on("click", (e) => {
				let text = $(e.target).text();
				frappe.utils.copy_to_clipboard(text);
			});
		}
	}

	render_timeline_items() {
		this.rendered_docname = this.frm.docname;
		this.active_comment_edit = null;
		this.keep_scroll_position(() => super.render_timeline_items());
		this.add_all_changes_link();
		const highlight = this.get_pending_highlight();
		highlight && this.flash_timeline_item(highlight.doctype, highlight.name);
		this.update_filter_empty_state();
		this.fit_file_lists();
		this.clamp_long_messages();
		this.setup_others_cards();
		this.add_web_page_view_count();
		frappe.utils.bind_actions_with_object(this.timeline_items_wrapper, this);
	}

	add_timeline_items_based_on_creation(items) {
		super.add_timeline_items_based_on_creation(items);
		this.apply_activity_filters();
		this.setup_others_cards();
	}

	add_all_changes_link() {
		this.all_changes_link?.remove();
		const versions = this.doc_info?.versions || [];
		if (versions.length < 10) return;
		this.all_changes_link = $(`<div class="timeline-all-changes"></div>`)
			.append(
				frappe.ui.button({
					label: __("View all changes", null, "Form timeline"),
					icon_right: "arrow-up-right",
					variant: "subtle",
					onclick: () =>
						frappe.set_route("List", "Version", {
							ref_doctype: this.frm.doctype,
							docname: this.frm.docname,
						}),
				})
			)
			.insertAfter(this.timeline_items_wrapper)
			.toggle(this.active_filter === "changes");
	}

	add_web_page_view_count() {
		if (this.frm.doc.route && cint(frappe.boot.website_tracking_enabled)) {
			frappe.utils.get_page_view_count(this.frm.doc.route).then((res) => {
				this.add_timeline_item({
					content: __("{0} Web page views", [res.message]),
					hide_timestamp: true,
				});
			});
		}
	}

	get_creation_message() {
		return {
			creation: this.frm.doc.creation,
			user: this.frm.doc.owner,
			icon: "plus",
			content: get_user_message(
				this.frm.doc.owner,
				__("You created this"),
				__("{0} created this", [get_user_link(this.frm.doc.owner)])
			),
		};
	}

	get_modified_message() {
		return {
			creation: this.frm.doc.modified,
			user: this.frm.doc.modified_by,
			icon: "pencil",
			content: get_user_message(
				this.frm.doc.modified_by,
				__("You last edited this"),
				__("{0} last edited this", [get_user_link(this.frm.doc.modified_by)])
			),
		};
	}

	prepare_timeline_contents() {
		this.timeline_items.push(this.get_creation_message());
		this.timeline_items.push(this.get_modified_message());
		this.timeline_items.push(...this.get_communication_timeline_contents());
		this.timeline_items.push(...this.get_comment_timeline_contents());
		this.timeline_items.push(...this.get_view_timeline_contents());
		this.timeline_items.push(...this.get_version_timeline_contents());
		this.timeline_items.push(...this.get_share_timeline_contents());
		this.timeline_items.push(...this.get_workflow_timeline_contents());
		this.timeline_items.push(...this.get_like_timeline_contents());
		this.timeline_items.push(...this.get_custom_timeline_contents());
		this.timeline_items.push(...this.get_assignment_timeline_contents());
		this.timeline_items.push(...this.get_attachment_timeline_contents());
		this.timeline_items.push(...this.get_info_timeline_contents());
		this.timeline_items.push(...this.get_milestone_timeline_contents());
	}

	get_view_timeline_contents() {
		let view_timeline_contents = [];
		(this.doc_info.views || []).forEach((view) => {
			view_timeline_contents.push({
				creation: view.creation,
				user: view.owner,
				icon: "eye",
				group: "views",
				content: get_user_message(
					view.owner,
					__("You viewed this"),
					__("{0} viewed this", [get_user_link(view.owner)])
				),
			});
		});

		return view_timeline_contents;
	}

	get_communication_timeline_contents(more_communications, more_automated_messages) {
		let email_communications =
			this.get_email_communication_timeline_contents(more_communications);
		let automated_messages = this.get_auto_messages_timeline_contents(more_automated_messages);
		let all_communications = email_communications.concat(automated_messages);

		if (all_communications.length > 20) {
			all_communications.pop();

			if (more_communications || more_automated_messages) {
				all_communications.forEach((message) => {
					if (message.communication_type == "Automated Message") {
						this.doc_info.automated_messages.push(message);
					} else {
						this.doc_info.communications.push(message);
					}
				});
			}

			let last_communication_time =
				all_communications[all_communications.length - 1].creation;
			let load_more_button = {
				creation: last_communication_time,
				content: __("Load More Communications", null, "Form timeline"),
				name: "load-more",
				category: "emails",
			};
			all_communications.push(load_more_button);
		}

		return all_communications;
	}

	get_email_communication_timeline_contents(more_items) {
		let communication_timeline_contents = [];
		let icon_set = {
			Email: "mail",
			Phone: "phone",
			Meeting: "calendar",
			Other: "ellipsis",
		};
		let items = more_items ? more_items : this.doc_info.communications || [];
		items.forEach((communication) => {
			let medium = communication.communication_medium;
			communication_timeline_contents.push({
				icon: icon_set[medium],
				icon_size: "sm",
				user: communication.sender,
				category: "emails",
				creation: communication.communication_date,
				is_card: true,
				show_timestamp: true,
				content: this.get_communication_timeline_content(communication),
				doctype: "Communication",
				id: `communication-${communication.name}`,
				name: communication.name,
			});
		});

		return communication_timeline_contents;
	}

	async get_more_communication_timeline_contents() {
		let more_items = [];
		let start =
			this.doc_info.communications.length + this.doc_info.automated_messages.length - 1;
		let response = await frappe.call({
			method: "frappe.desk.form.load.get_communications",
			args: {
				doctype: this.doc_info.doctype,
				name: this.doc_info.name,
				start: start,
				limit: 21,
			},
		});
		if (response.message) {
			let email_communications = [];
			let automated_messages = [];
			response.message.forEach((message) => {
				if (message.communication_type == "Automated Message") {
					automated_messages.push(message);
				} else {
					email_communications.push(message);
				}
			});
			more_items = this.get_communication_timeline_contents(
				email_communications,
				automated_messages
			);
		}
		return more_items;
	}

	get_communication_timeline_content(doc, allow_reply = true) {
		doc._url = frappe.utils.get_form_link("Communication", doc.name);
		this.set_communication_doc_status(doc);
		if (doc.attachments && typeof doc.attachments === "string") {
			doc.attachments = JSON.parse(doc.attachments);
		}
		doc.owner = doc.sender;
		doc.user_full_name = doc.sender_full_name;
		doc.content = frappe.dom.remove_script_and_style(doc.content);
		if (doc.communication_type == "Automated Message") {
			doc._summary = this.get_notification_summary(doc);
		}
		let communication_content = $(frappe.render_template("timeline_message_box", { doc }));
		if (allow_reply) {
			this.setup_reply(communication_content, doc);
		}
		this.setup_more_actions_menu(communication_content);
		return communication_content;
	}

	get_notification_summary(doc) {
		const emails = [
			...new Set(
				[doc.recipients, doc.cc, doc.bcc]
					.flatMap((value) => (value || "").split(","))
					.map((email) => email.trim())
					.filter(Boolean)
			),
		];
		const name = (email) =>
			`<span class="timeline-user-name">${frappe.utils.escape_html(
				frappe.user_info(email).fullname || email
			)}</span>`;
		const named = emails.length === 3 ? 3 : 2;
		const shown = emails.slice(0, named).map(name);
		if (emails.length > named) {
			const others = emails.slice(named).map((user) => ({ user }));
			shown.push(this.get_others_trigger(others.length, others));
		}
		return __("Notification sent to {0}", [frappe.utils.comma_and(shown)], "Form timeline");
	}

	set_communication_doc_status(doc) {
		let indicator_color = "red";
		if (["Sent", "Clicked"].includes(doc.delivery_status)) {
			indicator_color = "green";
		} else if (["Sending", "Scheduled"].includes(doc.delivery_status)) {
			indicator_color = "orange";
		} else if (["Opened", "Read"].includes(doc.delivery_status)) {
			indicator_color = "blue";
		} else if (doc.delivery_status == "Error") {
			indicator_color = "red";
		}
		doc._doc_status = doc.delivery_status;
		doc._doc_status_indicator = indicator_color;
	}

	get_auto_messages_timeline_contents(more_items) {
		let auto_messages_timeline_contents = [];
		let items = more_items ? more_items : this.doc_info.automated_messages || [];
		items.forEach((message) => {
			auto_messages_timeline_contents.push({
				icon: "bell",
				icon_size: "sm",
				category: "emails",
				creation: message.creation,
				content: this.get_communication_timeline_content(message, false),
				doctype: "Communication",
				name: message.name,
			});
		});
		return auto_messages_timeline_contents;
	}

	get_comment_timeline_contents() {
		let comment_timeline_contents = [];
		(this.doc_info.comments || [])
			.filter((comment) => !this.pending_deletes?.[comment.name])
			.forEach((comment) => {
				comment_timeline_contents.push(this.get_comment_timeline_item(comment));
			});
		return comment_timeline_contents;
	}

	get_comment_timeline_item(comment) {
		return {
			icon: "message-circle",
			icon_size: "sm",
			user: comment.owner,
			category: "comments",
			creation: comment.creation,
			doctype: "Comment",
			id: `comment-${comment.name}`,
			name: comment.name,
			content: this.get_comment_timeline_content(comment),
		};
	}

	get_comment_timeline_content(doc) {
		doc.content = frappe.dom.remove_script_and_style(doc.content);
		const author = frappe.utils.escape_html(
			doc.user_full_name || frappe.user.full_name(doc.owner)
		);
		doc._summary = get_user_message(
			doc.owner,
			__("You added a comment"),
			__("{0} added a comment", [`<span class="timeline-user-name">${author}</span>`])
		);
		const comment_content = $(frappe.render_template("timeline_message_box", { doc }));
		this.setup_comment_actions(comment_content, doc);
		this.setup_more_actions_menu(comment_content);
		return comment_content;
	}

	get_version_timeline_contents() {
		let version_timeline_contents = [];
		(this.doc_info.versions || []).forEach((version) => {
			const contents = get_version_timeline_content(version, this.frm);
			const changed = JSON.parse(version.data || "{}").changed;
			const docstatus = Array.isArray(changed)
				? changed.find((p) => p[0] === "docstatus")?.[2]
				: undefined;
			const docstatus_icon = { 1: "circle-check", 2: "circle-x" }[docstatus];
			contents.forEach((content, i) => {
				version_timeline_contents.push({
					creation: version.creation,
					user: version.owner,
					icon: (i === 0 && docstatus_icon) || "pencil",
					category: "changes",
					doctype: "Version",
					name: version.name,
					content: content,
				});
			});
		});
		return version_timeline_contents;
	}

	get_share_timeline_contents() {
		let share_timeline_contents = [];
		(this.doc_info.share_logs || []).forEach((share_log) => {
			share_timeline_contents.push({
				creation: share_log.creation,
				user: share_log.owner,
				icon: "share-2",
				content: share_log.content,
			});
		});
		return share_timeline_contents;
	}

	get_assignment_timeline_contents() {
		let assignment_timeline_contents = [];
		(this.doc_info.assignment_logs || []).forEach((assignment_log) => {
			assignment_timeline_contents.push({
				creation: assignment_log.creation,
				user: assignment_log.owner,
				icon: "user-plus",
				content: assignment_log.content,
			});
		});
		return assignment_timeline_contents;
	}

	get_info_timeline_contents() {
		let info_timeline_contents = [];
		(this.doc_info.info_logs || []).forEach((info_log) => {
			info_timeline_contents.push({
				creation: info_log.creation,
				user: info_log.owner,
				content: `${get_user_link(info_log.owner)} ${info_log.content}`,
			});
		});
		return info_timeline_contents;
	}

	get_attachment_timeline_contents() {
		let attachment_timeline_contents = [];

		(this.doc_info.attachment_logs || []).forEach((attachment_log) => {
			const is_file_upload = attachment_log.comment_type == "Attachment";
			const user_link = get_user_link(attachment_log.owner);
			const filename = `<span class="timeline-file">${frappe.utils.icon("file", "xs")}${
				attachment_log.content
			}</span>`;
			const timeline_content = is_file_upload
				? get_user_message(
						attachment_log.owner,
						__("You attached {0}", [filename], "Form timeline"),
						__("{0} attached {1}", [user_link, filename], "Form timeline")
				  )
				: get_user_message(
						attachment_log.owner,
						__("You removed attachment {0}", [filename], "Form timeline"),
						__("{0} removed attachment {1}", [user_link, filename], "Form timeline")
				  );

			attachment_timeline_contents.push({
				icon: is_file_upload ? "paperclip" : "trash",
				icon_size: "sm",
				user: attachment_log.owner,
				category: "attachments",
				creation: attachment_log.creation,
				content: timeline_content,
				group: `${is_file_upload ? "attached" : "removed"}:${attachment_log.owner}`,
				is_file_upload,
				file_chip: filename,
			});
		});

		return attachment_timeline_contents;
	}

	get_milestone_timeline_contents() {
		let milestone_timeline_contents = [];

		(this.doc_info.milestones || []).forEach((milestone_log) => {
			const field = frappe.meta.get_translated_label(
				this.frm.doctype,
				milestone_log.track_field
			);
			const value = frappe.utils.bold(milestone_log.value);
			const user_link = get_user_link(milestone_log.owner);
			const timeline_content = get_user_message(
				milestone_log.owner,
				__("You changed {0} to {1}", [field, value], "Form timeline"),
				__("{0} changed {1} to {2}", [user_link, field, value], "Form timeline")
			);

			milestone_timeline_contents.push({
				icon: "milestone",
				user: milestone_log.owner,
				category: "changes",
				creation: milestone_log.creation,
				content: timeline_content,
			});
		});

		return milestone_timeline_contents;
	}

	get_like_timeline_contents() {
		let like_timeline_contents = [];

		(this.doc_info.like_logs || []).forEach((like_log) => {
			const timeline_content = get_user_message(
				like_log.owner,
				__("You Liked"),
				__("{0} Liked", [get_user_link(like_log.owner)])
			);

			like_timeline_contents.push({
				icon: "heart",
				icon_size: "sm",
				user: like_log.owner,
				group: "likes",
				creation: like_log.creation,
				content: timeline_content,
				title: "Like",
			});
		});

		return like_timeline_contents;
	}

	get_workflow_timeline_contents() {
		let workflow_timeline_contents = [];
		(this.doc_info.workflow_logs || []).forEach((workflow_log) => {
			workflow_timeline_contents.push({
				icon: "git-branch",
				icon_size: "sm",
				user: workflow_log.owner,
				category: "changes",
				creation: workflow_log.creation,
				content: `${get_user_link(workflow_log.owner)} ${__(workflow_log.content)}`,
				title: "Workflow",
			});
		});
		return workflow_timeline_contents;
	}

	get_custom_timeline_contents() {
		let custom_timeline_contents = [];
		(this.doc_info.additional_timeline_content || []).forEach((custom_item) => {
			if (custom_item.timeline_badge) {
				custom_timeline_contents.push({
					timeline_badge: custom_item.timeline_badge,
					creation: custom_item.creation,
					content: frappe.utils.eval(custom_item.method, {
						custom_item: custom_item,
					}),
				});
			} else {
				custom_timeline_contents.push({
					icon: custom_item.icon,
					timeline_badge: custom_item.timeline_badge,
					icon_size: "sm",
					is_card: custom_item.is_card,
					creation: custom_item.creation,
					content:
						custom_item.content ||
						frappe.render_template(custom_item.template, custom_item.template_data),
				});
			}
		});
		return custom_timeline_contents;
	}

	setup_reply(communication_box, communication_doc) {
		let actions = communication_box.find(".custom-actions");
		// the action name stays the second class: add_dropdown_item labels from it
		let reply = frappe.ui.button({
			icon: "reply",
			variant: "ghost",
			tooltip: __("Reply"),
			css_class: "reply action-btn",
			onclick: () => this.compose_mail(communication_doc),
		});
		let reply_all = frappe.ui.button({
			icon: "reply-all",
			variant: "ghost",
			tooltip: __("Reply All"),
			css_class: "reply-all action-btn",
			onclick: () => this.compose_mail(communication_doc, true),
		});
		if (frappe.is_mobile()) {
			this.add_dropdown_item(communication_box, [reply, reply_all]);
		} else {
			actions.append(reply);
			actions.append(reply_all);
		}
	}
	setup_more_actions_menu(message_box) {
		message_box.find(".more-actions > .es-button, a.es-button[aria-label]").each((i, el) => {
			frappe.ui.tooltip($(el), { text: el.getAttribute("aria-label") });
		});

		// the template's .dropdown-menu stays as a hidden item store, so code
		// that appends items to it keeps working; the menu is built on open
		const trigger = message_box.find(".more-actions > .action-btn");
		const store = message_box.find(".more-actions > .dropdown-menu");
		if (!trigger.length) return;

		new frappe.ui.Dropdown({
			trigger,
			align: "end",
			options: () =>
				store
					.find(".dropdown-item")
					.toArray()
					.filter((el) => el.style.display !== "none" && el.textContent.trim())
					.map((el) => {
						const label = el.textContent.trim();
						const href = el.getAttribute("href");
						return href && href !== "#"
							? { label, href }
							: { label, onclick: () => el.click() };
					}),
		});
	}

	add_dropdown_item(timeline_box, menu_items) {
		let more_actions = timeline_box.find(".more-actions > .dropdown-menu > li");
		menu_items.forEach((m) => {
			let action_name = m[0].classList[1];
			let formatted_action_name =
				String(action_name).charAt(0).toUpperCase() + String(action_name).slice(1);
			m.empty();
			m.append(
				__("{0}", [frappe.utils.to_title_case(formatted_action_name.replace("-", " "))])
			);
			m.removeClass();
			m.addClass("dropdown-item");
			more_actions.append(m);
		});
	}
	compose_mail(communication_doc = null, reply_all = false) {
		const args = {
			doc: this.frm.doc,
			frm: this.frm,
			recipients:
				communication_doc && communication_doc.sender != frappe.session.user_email
					? communication_doc.sender
					: this.get_recipient(),
			is_a_reply: Boolean(communication_doc),
			title: communication_doc ? __("Reply") : null,
			last_email: communication_doc,
			subject: communication_doc && communication_doc.subject,
			reply_all: reply_all,
			sender: communication_doc?.sender,
		};

		const email_accounts = frappe.boot.email_accounts
			.filter((account) => {
				return (
					!["All Accounts", "Sent", "Spam", "Trash"].includes(account.email_account) &&
					account.enable_outgoing
				);
			})
			.map((e) => e.email_id);

		if (communication_doc && args.is_a_reply) {
			args.cc = "";
			if (
				email_accounts.includes(frappe.session.user_email) &&
				communication_doc.sender != frappe.session.user_email
			) {
				// add recipients to cc if replying sender is different from last email
				const recipients = communication_doc.recipients.split(",").map((r) => r.trim());
				args.cc =
					recipients.filter((r) => r != frappe.session.user_email).join(", ") + ", ";
			}
			if (reply_all) {
				// if reply_all then add cc and bcc as well.
				args.cc += cstr(communication_doc.cc);
				args.bcc = cstr(communication_doc.bcc);
			}
		}

		if (this.frm.doctype === "Communication") {
			args.message = "";
			args.last_email = this.frm.doc;
			args.recipients = this.frm.doc.sender;
			args.subject = __("Re: {0}", [this.frm.doc.subject]);
		} else {
			const comment_value = frappe.markdown(this.frm.comment_box.get_value());
			args.message = strip_html(comment_value) ? comment_value : "";
		}

		new frappe.views.CommunicationComposer(args);
	}

	get_recipient() {
		if (this.frm.email_field) {
			return this.frm.doc[this.frm.email_field];
		} else {
			return this.frm.doc.email_id || this.frm.doc.email || "";
		}
	}

	setup_comment_actions(comment_wrapper, doc) {
		let edit_wrapper = $(`<div class="comment-edit-box">`).hide();
		let edit_box = this.make_editable(edit_wrapper);
		let content_wrapper = comment_wrapper.find(".content");
		let more_actions_wrapper = comment_wrapper.find(".more-actions");
		const dropdown_menu = more_actions_wrapper.find(".dropdown-menu li");

		let current_user = frappe.session.user;
		let can_edit = ["Administrator", doc.owner].includes(current_user);
		if (can_edit) {
			$(`<a class="dropdown-item">${__("Edit")}</a>`)
				.click(() => this.start_comment_edit(editor))
				.appendTo(dropdown_menu);
		}

		if (frappe.session.user == doc.owner || frappe.user.has_role("System Manager")) {
			if (frappe.model.can_delete("Comment")) {
				const delete_option = $(`
					<a class="dropdown-item">${__("Delete")}</a>
				`).click(() => this.delete_comment(doc.name));
				dropdown_menu.append(delete_option);
			}

			const un_publish_button = $(`
				<a class="dropdown-item">${doc.published ? __("Unpublish") : __("Publish")}</a>
			`).click(() => this.update_comment_publicity(doc.name, !doc.published));
			dropdown_menu.append(un_publish_button);
		}

		let dismiss_button = frappe.ui
			.button({
				label: __("Cancel"),
				css_class: "action-btn",
				onclick: () => edit_button.toggle_edit_mode(),
			})
			.hide();

		edit_box.set_value(doc.content);

		edit_box.on_submit = (value) => {
			content_wrapper.empty();
			content_wrapper.append(value);
			edit_button.prop("disabled", true);
			edit_box.quill.enable(false);

			doc.content = value;
			this.update_comment(doc.name, value)
				.then(() => {
					edit_button.toggle_edit_mode();
					frappe.ui.toast({ message: __("Comment updated"), type: "success" });
					this.highlight_timeline_item("Comment", doc.name);
				})
				.finally(() => {
					edit_button.prop("disabled", false);
					edit_box.quill.enable(true);
				});
		};

		content_wrapper.after(edit_wrapper);

		let edit_button = $();
		if (can_edit) {
			edit_button = frappe.ui
				.button({
					label: __("Save"),
					variant: "solid",
					css_class: "edit action-btn",
					onclick: () => edit_box.submit(),
				})
				.hide();
		}

		const editor = {
			is_open: () => Boolean(edit_button.edit_mode),
			open: () => !edit_button.edit_mode && edit_button.toggle_edit_mode(),
			close: () => edit_button.edit_mode && edit_button.toggle_edit_mode(),
			has_changes: () =>
				edit_button.edit_mode && edit_button.initial_value !== edit_box.get_value(),
			focus: () => edit_box.quill?.focus(),
		};

		edit_button.toggle_edit_mode = () => {
			edit_button.edit_mode = !edit_button.edit_mode;
			if (edit_button.edit_mode) {
				edit_button.initial_value = edit_box.get_value();
			} else if (this.active_comment_edit === editor) {
				this.active_comment_edit = null;
			}
			edit_button.toggle(edit_button.edit_mode);
			more_actions_wrapper.toggle(!edit_button.edit_mode);
			dismiss_button.toggle(edit_button.edit_mode);
			edit_wrapper.toggle(edit_button.edit_mode);
			content_wrapper.toggle(!edit_button.edit_mode);
			comment_wrapper
				.find(".timeline-message-card")
				.toggleClass("timeline-message-card-editing", edit_button.edit_mode);
			if (edit_button.edit_mode) {
				const quill = edit_box.quill;
				setTimeout(() => {
					quill?.focus();
					quill?.setSelection(quill.getLength(), 0);
				});
			}
			if (!edit_button.edit_mode && this.refresh_pending) {
				this.refresh();
			}
		};
		comment_wrapper.find(".custom-actions").append(dismiss_button, edit_button);
	}

	start_comment_edit(editor) {
		const current = this.active_comment_edit;
		const open = () => {
			if (current !== editor) current?.close();
			this.active_comment_edit = editor;
			editor.open();
		};
		if (!current || current === editor || !current.has_changes()) {
			return open();
		}
		frappe.confirm(__("Discard your unsaved changes to the other comment?"), open, () =>
			current.focus()
		);
	}

	make_editable(container) {
		return frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: "Comment",
				fieldname: "comment",
				label: "Comment",
			},
			enable_mentions: true,
			render_input: true,
			only_input: true,
			no_wrapper: true,
		});
	}

	update_comment(name, content) {
		return frappe
			.xcall("frappe.desk.form.utils.update_comment", { name, content })
			.then(() => {
				frappe.utils.play_sound("click");
			});
	}

	get_last_email(from_recipient) {
		/**
		 * Return the latest email communication.
		 *
		 * @param {boolean} from_recipient If true, only considers emails where current form's recipient is the sender.
		 * @returns {object|null} The latest email communication, or null if no communication is found.
		 */

		const communications = this.frm.get_docinfo().communications || [];
		const recipient = this.get_recipient();

		const filtered_records = communications
			.filter(
				(record) =>
					record.communication_type === "Communication" &&
					record.communication_medium === "Email" &&
					(!from_recipient || record.sender === recipient)
			)
			.sort((a, b) => b.creation - a.creation);

		return filtered_records[0] || null;
	}

	delete_comment(comment_name) {
		this.pending_deletes = this.pending_deletes || {};
		if (this.pending_deletes[comment_name]) return;
		const toast = frappe.ui.toast({
			message: __("Comment deleted"),
			icon: "trash-2",
			icon_class: "timeline-toast-danger-icon",
			duration: 5000,
			action: { label: __("Undo"), onclick: () => this.undo_comment_delete(comment_name) },
		});
		const pending = { toast };
		const start_timer = () => {
			clearTimeout(pending.timer);
			pending.timer = setTimeout(() => {
				this.pending_deletes[comment_name] === pending &&
					this.finish_comment_delete(comment_name);
			}, 5000);
		};
		toast.$el.on("mouseenter focusin", () => clearTimeout(pending.timer));
		toast.$el.on("mouseleave focusout", start_timer);
		start_timer();
		this.pending_deletes[comment_name] = pending;
		this.find_timeline_item("Comment", comment_name)?.classList.add("timeline-item-deleted");
		this.update_filter_empty_state();
	}

	finish_comment_delete(comment_name) {
		const pending = this.pending_deletes?.[comment_name];
		if (!pending) return;
		clearTimeout(pending.timer);
		// after leaving the form the toast would offer an undo that can't happen
		pending.toast.dismiss();
		delete this.pending_deletes[comment_name];
		return frappe
			.xcall("frappe.client.delete", { doctype: "Comment", name: comment_name })
			.then(() => frappe.utils.play_sound("delete"))
			.catch(() => this.render_timeline_items());
	}

	undo_comment_delete(comment_name) {
		const pending = this.pending_deletes?.[comment_name];
		if (!pending) return;
		clearTimeout(pending.timer);
		pending.toast.dismiss();
		delete this.pending_deletes[comment_name];
		const el = this.find_timeline_item("Comment", comment_name);
		el ? el.classList.remove("timeline-item-deleted") : this.render_timeline_items();
		this.update_filter_empty_state();
		this.highlight_timeline_item("Comment", comment_name);
	}

	send_pending_deletes() {
		// the page is going away: a request that outlives it, since a normal
		// call would be cancelled and the comment would come back
		Object.keys(this.pending_deletes || {}).forEach((name) => {
			clearTimeout(this.pending_deletes[name].timer);
			delete this.pending_deletes[name];
			fetch("/api/method/frappe.client.delete", {
				method: "POST",
				keepalive: true,
				headers: {
					"Content-Type": "application/json",
					"X-Frappe-CSRF-Token": frappe.csrf_token,
				},
				body: JSON.stringify({ doctype: "Comment", name }),
			});
		});
	}

	flush_comment_deletes() {
		Object.keys(this.pending_deletes || {}).forEach((name) =>
			this.finish_comment_delete(name)
		);
	}

	update_comment_publicity(comment_name, publish) {
		let message;
		if (publish) {
			message = __(
				"Would you like to publish this comment? This means it will become visible to website/portal users."
			);
		} else {
			message = __(
				"Would you like to unpublish this comment? This means it will no longer be visible to website/portal users."
			);
		}

		frappe.confirm(message, () => {
			return frappe
				.xcall("frappe.desk.form.utils.update_comment_publicity", {
					name: comment_name,
					publish,
				})
				.then(() => {
					frappe.utils.play_sound("click");
				});
		});
	}

	copy_link(ev) {
		let doc_link = frappe.urllib.get_full_url(
			frappe.utils.get_form_link(this.frm.doctype, this.frm.docname)
		);
		let element_id = $(ev.currentTarget).closest(".timeline-content").attr("id");
		frappe.utils.copy_to_clipboard(`${doc_link}#${element_id}`);
	}
}

export default FormTimeline;
