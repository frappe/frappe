frappe.provide("frappe.search");

frappe.ui.Notifications = class Notifications {
	constructor() {
		this.tabs = {};
		this.notification_settings = frappe.boot.notification_settings;
		this.make();
	}

	make() {
		this.dropdown = $(".navbar").find(".dropdown-notifications").removeClass("hidden");
		this.dropdown_list = this.dropdown.find(".notifications-list");
		this.header_items = this.dropdown_list.find(".header-items");
		this.header_actions = this.dropdown_list.find(".header-actions");
		this.body = this.dropdown_list.find(".notification-list-body");
		this.panel_events = this.dropdown_list.find(".panel-events");
		this.panel_notifications = this.dropdown_list.find(".panel-notifications");
		this.panel_changelog_feed = this.dropdown_list.find(".panel-changelog-feed");

		this.user = frappe.session.user;

		this.setup_headers();
		this.setup_dropdown_events();
	}

	setup_headers() {
		// Add header actions
		$(`<span class="notification-settings pull-right" data-action="go_to_settings">
			${frappe.utils.icon("setting-gear")}
		</span>`)
			.on("click", (e) => {
				e.stopImmediatePropagation();
				this.dropdown.dropdown("hide");
				frappe.set_route("Form", "Notification Settings", frappe.session.user);
			})
			.appendTo(this.header_actions)
			.attr("title", __("Notification Settings"))
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		$(`<span class="mark-all-read pull-right" data-action="mark_all_as_read">
			${frappe.utils.icon("mark-as-read")}
		</span>`)
			.on("click", (e) => this.mark_all_as_read(e))
			.appendTo(this.header_actions)
			.attr("title", __("Mark all as read"))
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		this.categories = [
			{
				label: __("Notifications"),
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
			{
				label: __("What's New"),
				id: "changelog_feed",
				view: ChangelogFeedView,
				el: this.panel_changelog_feed,
			},
		];

		let get_headers_html = (item) => {
			let active = item.id == "notifications" ? "active" : "";

			return `<li class="notifications-category ${active}"
   					id="${item.id}"
   					data-toggle="collapse"
   				>${item.label}</li>`;
		};

		let navitem = $(`<ul class="notification-item-tabs nav nav-tabs" role="tablist"></ul>`);
		this.categories = this.categories.map((item) => {
			item.$tab = $(get_headers_html(item));
			item.$tab.on("click", (e) => {
				e.stopImmediatePropagation();
				this.switch_tab(item);
			});
			navitem.append(item.$tab);

			return item;
		});
		navitem.appendTo(this.header_items);
		this.categories.forEach((category) => {
			this.make_tab_view(category);
		});
		this.switch_tab(this.categories[0]);
	}

	switch_tab(item) {
		// Set active tab
		this.categories.forEach((item) => {
			item.$tab.removeClass("active");
		});

		item.$tab.addClass("active");

		// Hide other tabs
		Object.keys(this.tabs).forEach((tab_name) => this.tabs[tab_name].hide());
		this.tabs[item.id].show();
	}

	make_tab_view(item) {
		let tabView = new item.view(item.el, this.dropdown, this.notification_settings);
		this.tabs[item.id] = tabView;
	}

	mark_all_as_read(e) {
		e.stopImmediatePropagation();
		this.dropdown_list.find(".unread").removeClass("unread");
		frappe.call("frappe.desk.doctype.notification_log.notification_log.mark_all_as_read");
	}

	setup_dropdown_events() {
		this.dropdown.on("hide.bs.dropdown", (e) => {
			let hide = $(e.currentTarget).data("closable");
			$(e.currentTarget).data("closable", true);
			return hide;
		});

		this.dropdown.on("click", (e) => {
			$(e.currentTarget).data("closable", true);
		});
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
}

class NotificationsView extends BaseNotificationsView {
	make() {
		this.notifications_icon = this.parent.find(".notifications-icon");
		this.notifications_icon
			.attr("title", __("Notifications"))
			.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });

		this.setup_notification_listeners();
		this.get_notifications_list(this.max_length).then((r) => {
			if (!r.message) return;
			this.dropdown_items = r.message.notification_logs;
			frappe.update_user_info(r.message.user_info);
			this.render_notifications_dropdown();
			if (this.settings.seen == 0 && this.dropdown_items.length > 0) {
				this.toggle_notification_icon(false);
			}
		});
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
					href="/app/List/Notification Log">
					<div class="full-log-btn">${__("View Full Log")}</div>
				</a>`
			);
		}
	}

	mark_as_read(docname, $el) {
		frappe
			.call("frappe.desk.doctype.notification_log.notification_log.mark_as_read", {
				docname: docname,
			})
			.then(() => {
				$el.removeClass("unread");
			});
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
		let message = notification_log.subject;

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

		let item_html = $(`<a class="recent-item notification-item ${read_class}"
				href="${doc_link}"
				data-name="${notification_log.name}"
			>
				<div class="notification-body">
					${user_avatar}
					${message_html}
				</div>
				<div class="mark-as-read" title="${__("Mark as Read")}">
				</div>
			</a>`);

		if (!notification_log.read) {
			let mark_btn = item_html.find(".mark-as-read");
			mark_btn.tooltip({ delay: { show: 600, hide: 100 }, trigger: "hover" });
			mark_btn.on("click", (e) => {
				e.preventDefault();
				e.stopImmediatePropagation();
				this.mark_as_read(notification_log.name, item_html);
			});
		}

		item_html.on("click", () => {
			!notification_log.read && this.mark_as_read(notification_log.name, item_html);
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
					href="/app/List/Notification Log">
						<div class="full-log-btn">${__("See all Activity")}</div>
					</a>`);
			} else {
				this.container.append(
					$(`<div class="notification-null-state">
					<div class="text-center">
						<img src="/assets/frappe/images/ui-states/notification-empty-state.svg" alt="Generic Empty State" class="null-state">
						<div class="title">${__("No New notifications")}</div>
						<div class="subtitle">
							${__("Looks like you haven’t received any notifications.")}
					</div></div></div>`)
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
		return frappe.utils.get_form_link(link_doctype, link_docname);
	}

	toggle_notification_icon(seen) {
		this.notifications_icon.find(".notifications-seen").toggle(seen);
		this.notifications_icon.find(".notifications-unseen").toggle(!seen);
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
			this.toggle_notification_icon(false);
			this.update_dropdown();
		});

		frappe.realtime.on("indicator_hide", () => {
			this.toggle_notification_icon(true);
		});

		this.parent.on("show.bs.dropdown", () => {
			this.toggle_seen(true);
			if (this.notifications_icon.find(".notifications-unseen").is(":visible")) {
				this.toggle_notification_icon(true);
				frappe.call(
					"frappe.desk.doctype.notification_log.notification_log.trigger_indicator_hide"
				);
			}
		});
	}
}

class EventsView extends BaseNotificationsView {
	make() {
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
			});
	}

	render_events_html(event_list) {
		let html = "";
		if (event_list.length) {
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
					location = `, ${event.location}`;
				}

				return `<a class="recent-item event" href="/app/event/${event.name}">
					<div class="event-border" style="border-color: ${event.color}"></div>
					<div class="event-item">
						<div class="event-subject">${event.subject}</div>
						<div class="event-time">${time}${location}</div>
						${particpants}
					</div>
				</a>`;
			};
			html = event_list.map(get_event_html).join("");
		} else {
			html = `
				<div class="notification-null-state">
					<div class="text-center">
					<img src="/assets/frappe/images/ui-states/event-empty-state.svg" alt="Generic Empty State" class="null-state">
					<div class="title">${__("No Upcoming Events")}</div>
					<div class="subtitle">
						${__("There are no upcoming events for you.")}
				</div></div></div>
			`;
		}

		this.container.html(html);
	}
}

class ChangelogFeedView extends BaseNotificationsView {
	make() {
		this.render_changelog_feed_html(frappe.boot.changelog_feed || []);
	}

	render_changelog_feed_html(changelog_feed) {
		let html = "";
		if (changelog_feed.length) {
			this.container.empty();
			const get_changelog_feed_html = (changelog_feed_item) => {
				const timestamp = frappe.datetime.prettyDate(
					changelog_feed_item.posting_timestamp
				);
				const message_html = `<div class="message">
							<div>${changelog_feed_item.title}</div>
							<div class="notification-timestamp text-muted">
							${changelog_feed_item.app_title} | ${timestamp}
							</div>
						</div>`;

				const item_html = `<a class="recent-item notification-item"
								href="${changelog_feed_item.link}"
								data-name="${changelog_feed_item.title}"
								target="_blank" rel="noopener noreferrer"
							>
							<div class="notification-body">
								${message_html}
							</div>
							</div>
						</a>`;

				return item_html;
			};
			html = changelog_feed.map(get_changelog_feed_html).join("");
		} else {
			html = `<div class="notification-null-state">
						<div class="text-center">
							<img src="/assets/frappe/images/ui-states/notification-empty-state.svg" alt="Generic Empty State" class="null-state">
							<div class="title">${__("Nothing New")}</div>
							<div class="subtitle">
								${__("There is nothing new to show you right now.")}
							</div>
						</div>
					</div>
					`;
		}
		this.container.html(html);
	}
}
