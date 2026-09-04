frappe.provide("frappe.search");

frappe.ui.Notifications = class Notifications {
	constructor(opts) {
		this.tabs = {};
		this.notification_settings = frappe.boot.notification_settings;
		// Two hosts. The sidebar bell opens a frappe.ui.SidebarPanel; the desk bell opens
		// a popover, which brings its own surface and its own dismissal. The heading and
		// the tab bodies below are the same either way.
		this.as_popover = opts?.popover || false;

		this.wrapper = opts?.wrapper || $(".body-sidebar");
		this.make();
	}

	make() {
		this.wrapper.find(".sidebar-notification").removeClass("hidden");
		this.user = frappe.session.user;

		if (this.as_popover) {
			this.make_popover_host();
		} else {
			this.make_panel_host();
		}

		this.setup_header_actions();
		this.setup_tabs();
	}

	/**
	 * Sidebar host. The panel supplies the surface and the heading, and dismissal is
	 * frappe.ui.sidebar_panels' job, so there is nothing to wire up here beyond saying
	 * what goes in the body.
	 */
	make_panel_host() {
		this.panel = new frappe.ui.SidebarPanel({
			name: "notifications",
			title: __("Notifications"),
			trigger_selector: ".sidebar-notification",
			on_open: () => this.on_open(),
		});
		this.$host = this.panel.$panel;
		this.header_items = this.panel.$items;
		this.header_actions = this.panel.$actions;
		this.render_body().appendTo(this.panel.$body);
	}

	/**
	 * Desk host. There is only a bell here, so the heading and the body are built into a
	 * content element and handed to the popover, which supplies the surface itself.
	 */
	make_popover_host() {
		const header = frappe.ui.panel_header({
			title: __("Notifications"),
			on_close: () => this.close_panel(),
		});
		this.header_items = header.$items;
		this.header_actions = header.$actions;

		this.$list = $(`<div class="notifications-list"></div>`)
			.append(header.$header)
			.append(this.render_body());
		this.$host = this.wrapper;

		this.popover = new frappe.ui.Popover({
			trigger: this.wrapper.find(".desktop-notification-icon"),
			// the same element every time, so the fetched list and the selected tab
			// survive a close/open round trip
			content: () => this.$list[0],
			css_class: "notifications-popover",
			side: "bottom",
			align: "end",
			on_open: () => this.on_open(),
		});

		// The panel host gets this from the registry; the popover has no notion of routing.
		$(document).on("page-change", () => this.close_panel());
	}

	/** Fanned out to the views so neither of them has to know how it was opened. */
	on_open() {
		Object.keys(this.tabs).forEach((tab_name) => this.tabs[tab_name].on_open());
	}

	close_panel() {
		if (this.as_popover) {
			this.popover?.close();
		} else {
			this.panel?.hide();
		}
	}

	/** The tab bodies. Everything around them belongs to whichever host is in use. */
	render_body() {
		this.body = $(`
			<div class="notification-list-body">
				<div class="panel-notifications"></div>
				<div class="panel-events"></div>
			</div>
		`);
		this.panel_events = this.body.find(".panel-events");
		this.panel_notifications = this.body.find(".panel-notifications");
		return this.body;
	}

	setup_header_actions() {
		let add_action = ({ css_class, icon, title, on_click }) => {
			let $action = $(
				`<span class="${css_class}">${frappe.utils.icon(
					icon,
					"sm",
					"",
					"",
					"current-color",
					true
				)}</span>`
			)
				.on("click", on_click)
				.appendTo(this.header_actions);

			if (title) {
				$action
					.attr("title", title)
					.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });
			}
			return $action;
		};

		add_action({
			css_class: "notification-settings",
			icon: "settings",
			title: __("Notification Settings"),
			on_click: (e) => {
				e.stopImmediatePropagation();
				frappe.set_route("Form", "Notification Settings", frappe.session.user);
			},
		});

		add_action({
			css_class: "mark-all-read",
			icon: "check-check",
			title: __("Mark all as read"),
			on_click: (e) => this.mark_all_as_read(e),
		});
	}

	setup_tabs() {
		this.categories = [
			{
				label: __("All"),
				id: "notifications",
				view: NotificationsView,
				el: this.panel_notifications,
			},
			{
				label: __("Events"),
				id: "todays_events",
				view: EventsView,
				el: this.panel_events,
			},
		];

		this.categories.forEach((category) => this.make_tab_view(category));

		// es-tab-buttons owns the segmented look, the radio-group semantics and the
		// arrow-key navigation, so none of that is reimplemented here.
		frappe.ui
			.tab_buttons({
				label: __("Notification categories"),
				options: this.categories.map(({ label, id }) => ({ label, value: id })),
				value: this.categories[0].id,
				on_change: (id) => this.switch_tab(id),
			})
			.appendTo(this.header_items);

		this.switch_tab(this.categories[0].id);
	}

	switch_tab(id) {
		Object.keys(this.tabs).forEach((tab_name) => this.tabs[tab_name].hide());
		this.tabs[id].show();
	}

	make_tab_view(item) {
		let tabView = new item.view(item.el, this.$host, this.notification_settings);
		this.tabs[item.id] = tabView;
	}

	mark_all_as_read(e) {
		e.stopImmediatePropagation();
		this.body.find(".unread").removeClass("unread");
		frappe.call("frappe.desk.doctype.notification_log.notification_log.mark_all_as_read");
		this.tabs.notifications?.update_count_badge(0);
	}
};

frappe.ui.notifications = {
	get_notification_config() {
		return frappe.xcall("frappe.desk.notifications.get_notification_info").then((r) => {
			frappe.ui.notifications.config = r;
			return r;
		});
	},

	show_open_count_list(doctype) {
		if (!frappe.ui.notifications.config) {
			this.get_notification_config().then(() => {
				this.route_to_list_with_filters(doctype);
			});
		} else {
			this.route_to_list_with_filters(doctype);
		}
	},

	route_to_list_with_filters(doctype) {
		let filters = frappe.ui.notifications.config["conditions"][doctype];
		if (filters && $.isPlainObject(filters)) {
			if (!frappe.route_options) {
				frappe.route_options = {};
			}
			$.extend(frappe.route_options, filters);
		}
		frappe.set_route("List", doctype);
	},
};

// Both panels fill the same amount of the body, so their empty and loading
// states are built from one place and given the same min-height.
const NULL_STATE_CLASS = "min-h-80";

function get_null_state_html(icon, title, description) {
	return frappe.ui.empty_state.html({
		icon,
		title,
		description,
		css_class: NULL_STATE_CLASS,
	});
}

function get_loading_state_html() {
	return `<div class="flex items-center justify-center ${NULL_STATE_CLASS}">
		<span class="es-spinner" aria-label="${__("Loading")}"></span>
	</div>`;
}

class BaseNotificationsView {
	constructor(wrapper, parent, settings) {
		// wrapper, max_length
		this.wrapper = wrapper;
		this.parent = parent;
		this.settings = settings;
		this.max_length = 20;
		this.container = $(`<div></div>`).appendTo(this.wrapper);
		this.make();
	}

	show() {
		this.container.show();
	}

	hide() {
		this.container.hide();
	}

	/** Called every time the panel opens, whichever host it lives in. */
	on_open() {}
}

class NotificationsView extends BaseNotificationsView {
	make() {
		this.notifications_icon = this.parent.find(".notifications-icon");
		this.notifications_icon
			.attr("title", __("Notifications"))
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		this.setup_notification_listeners();

		this.dropdown_items = [];
		this.notifications_fetched = false;
		this.unread_count = frappe.boot.notification_unread_count || 0;

		this.update_count_badge(this.unread_count);
	}

	update_dropdown() {
		this.get_notifications_list(1).then((r) => {
			if (!r.message) return;
			let new_item = r.message.notification_logs[0];
			frappe.update_user_info(r.message.user_info);
			this.dropdown_items.unshift(new_item);
			if (this.dropdown_items.length > this.max_length) {
				this.container.find(".recent-notification").last().remove();
				this.dropdown_items.pop();
			}

			this.insert_into_dropdown();
		});
	}

	change_activity_status() {
		if (this.container.find(".activity-status")) {
			this.container.find(".activity-status").replaceWith(
				`<a class="recent-item text-center text-muted"
					href="/desk/List/Notification Log">
					<div class="full-log-btn">${__("View Full Log")}</div>
				</a>`
			);
		}
	}

	insert_into_dropdown() {
		let new_item = this.dropdown_items[0];
		let new_item_html = this.get_dropdown_item_html(new_item);
		$(new_item_html).prependTo(this.container);
		this.change_activity_status();
	}

	get_dropdown_item_html(notification_log) {
		let doc_link = this.get_item_link(notification_log);

		let read_class = notification_log.read ? "" : "unread";
		// Title/Description are the canonical fields; fall back to the legacy subject/content.
		let message = notification_log.title || notification_log.subject || "";

		let title = message.match(/<b class="subject-title">(.*?)<\/b>/);
		message = title
			? message.replace(title[1], frappe.ellipsis(strip_html(title[1]), 100))
			: message;

		let timestamp = frappe.datetime.comment_when(notification_log.creation);
		let message_html = `<div class="message">
			<div>${message}</div>
			<div class="notification-timestamp text-muted">
				${timestamp}
			</div>
		</div>`;

		let user = notification_log.from_user;
		let user_avatar = frappe.avatar(user, "avatar-medium user-avatar");

		// Unread is indicated but not individually dismissible -- the only way to
		// clear it is "Mark all as read" in the header.
		let item_html = $(`<a class="recent-item notification-item ${read_class}"
				href="${doc_link}"
				data-name="${notification_log.name}"
			>
				<div class="notification-body">
					${user_avatar}
					${message_html}
				</div>
			</a>`);

		item_html.on("click", () => {
			this.notifications_icon.trigger("click");
		});

		return item_html;
	}

	render_notifications_dropdown() {
		if (this.settings && !this.settings.enabled) {
			this.container.html(`<li class="recent-item notification-item">
				<span class="text-muted">
					${__("Notifications Disabled")}
				</span></li>`);
		} else {
			if (this.dropdown_items.length) {
				this.container.empty();
				this.dropdown_items.forEach((notification_log) => {
					this.container.append(this.get_dropdown_item_html(notification_log));
				});
				this.container.append(`<a class="list-footer"
					href="/desk/List/Notification Log">
						<div class="full-log-btn">${__("See all Activity")}</div>
					</a>`);
			} else {
				this.container.html(
					get_null_state_html(
						"bell",
						__("No New Notifications"),
						__("You have no new notifications")
					)
				);
			}
		}
	}

	get_notifications_list(limit) {
		return frappe.call({
			method: "frappe.desk.doctype.notification_log.notification_log.get_notification_logs",
			args: { limit: limit },
			type: "GET",
			cache: true,
		});
	}

	get_item_link(notification_doc) {
		if (notification_doc.link) {
			return notification_doc.link;
		}
		const link_doctype = notification_doc.document_type
			? notification_doc.document_type
			: "Notification Log";
		const link_docname = notification_doc.document_name
			? notification_doc.document_name
			: notification_doc.name;
		const form_link = frappe.utils.get_form_link(link_doctype, link_docname);
		// the timeline renders each entry with `id="<doctype>-<name>"`, so the
		// source record anchors the link to the exact spot in the document
		if (notification_doc.source_doctype && notification_doc.source_name) {
			const anchor = `${frappe.scrub(notification_doc.source_doctype)}-${
				notification_doc.source_name
			}`;
			return `${form_link}#${anchor}`;
		}
		return form_link;
	}

	update_count_badge(count) {
		this.unread_count = count;
		// the unread count is the only unread affordance any bell gets -- update it wherever a bell
		// lives (sidebar, dock, desktop navbar). Re-queried each call so it also covers
		// bells created after this view (the dock).
		const $count = $(".notification-count");
		if (!$count.length) return;

		if (count > 0) {
			$count
				.text(count > 99 ? "99+" : count)
				.attr("aria-label", __("{0} unread notifications", [count]))
				.removeClass("hidden");
		} else {
			$count.removeAttr("aria-label").addClass("hidden");
		}
	}

	toggle_seen(flag) {
		frappe.call(
			"frappe.desk.doctype.notification_settings.notification_settings.set_seen_value",
			{
				value: cint(flag),
				user: frappe.session.user,
			}
		);
	}

	setup_notification_listeners() {
		frappe.realtime.on("notification", () => {
			this.settings.seen = 0;
			this.update_count_badge(this.unread_count + 1);
			this.update_dropdown();
		});

		frappe.realtime.on("indicator_hide", () => {
			this.settings.seen = 1;
		});
	}

	on_open() {
		if (!this.notifications_fetched) {
			this.container.html(get_loading_state_html());
			this.get_notifications_list(this.max_length).then((r) => {
				if (r.message && r.message.notification_logs) {
					this.dropdown_items = r.message.notification_logs;
					frappe.update_user_info(r.message.user_info);
				} else {
					this.dropdown_items = [];
				}
				this.render_notifications_dropdown();
				this.notifications_fetched = true;
			});
		}

		this.toggle_seen(true);
		// opening the panel counts as seeing what's in it -- let the other sessions know
		if (this.settings?.seen == 0) {
			this.settings.seen = 1;
			frappe.call(
				"frappe.desk.doctype.notification_log.notification_log.trigger_indicator_hide"
			);
		}
	}
}

class EventsView extends BaseNotificationsView {
	make() {
		this.events_fetched = false;
	}

	on_open() {
		if (this.events_fetched) return;

		this.container.html(get_loading_state_html());

		let today = frappe.datetime.get_today();
		frappe
			.xcall(
				"frappe.desk.doctype.event.event.get_events",
				{
					start: today,
					end: today,
				},
				"GET",
				{ cache: true }
			)
			.then((event_list) => {
				this.render_events_html(event_list);
				this.events_fetched = true;
			});
	}

	render_events_html(event_list) {
		if (!event_list.length) {
			this.container.html(
				get_null_state_html(
					"calendar",
					__("No Upcoming Events"),
					__("There are no upcoming events for you.")
				)
			);
			return;
		}

		let get_event_html = (event) => {
			let time = __("All Day");
			if (!event.all_day) {
				let start_time = frappe.datetime.get_time(event.starts_on);
				let days_diff = frappe.datetime.get_day_diff(event.ends_on, event.starts_on);
				let end_time = frappe.datetime.get_time(event.ends_on);
				if (days_diff > 1) {
					end_time = __("Rest of the day");
				}
				time = `${start_time} - ${end_time}`;
			}

			// REDESIGN-TODO: Add Participants to get_events query
			let particpants = "";
			if (event.particpants) {
				particpants = frappe.avatar_group(event.particpants, 3);
			}

			// REDESIGN-TODO: Add location to calendar field
			let location = "";
			if (event.location) {
				location = `, ${frappe.utils.escape_html(event.location)}`;
			}

			let starts_on = moment(event.starts_on);
			let dot_style = event.color
				? ` style="background-color: ${frappe.utils.escape_html(event.color)}"`
				: "";

			return `<a class="recent-item event" href="/desk/event/${frappe.utils.escape_html(
				event.name
			)}">
				<div class="event-date">
					<div class="event-date-month">${starts_on.format("MMM")}</div>
					<div class="event-date-day">${starts_on.format("DD")}</div>
				</div>
				<div class="event-item">
					<div class="event-subject-row">
						<span class="event-dot"${dot_style}></span>
						<span class="event-subject">${frappe.utils.escape_html(event.subject)}</span>
					</div>
					<div class="event-time">${time}${location}</div>
					${particpants}
				</div>
			</a>`;
		};

		let $section = $(`<div class="event-group">
			<div class="event-group-header" role="button" tabindex="0" aria-expanded="true">
				${frappe.utils.icon("chevron-down", "sm", "", "", "event-group-chevron current-color", true)}
				<span class="event-group-label">${__("Upcoming events")}</span>
				<span class="event-group-count">${event_list.length}</span>
			</div>
			<div class="event-group-items">
				${event_list.map(get_event_html).join("")}
			</div>
		</div>`);

		let toggle_group = () => {
			let collapsed = $section.toggleClass("collapsed").hasClass("collapsed");
			$section.find(".event-group-header").attr("aria-expanded", !collapsed);
		};

		$section.find(".event-group-header").on("click", toggle_group);
		$section.find(".event-group-header").on("keydown", (e) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				toggle_group();
			}
		});

		this.container.empty().append($section);
	}
}
