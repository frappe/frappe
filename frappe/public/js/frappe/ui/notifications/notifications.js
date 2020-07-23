frappe.provide('frappe.search');

frappe.ui.Notifications = class Notifications {
	constructor() {
		this.tabs = {};
		frappe.model
			.with_doc('Notification Settings', frappe.session.user)
			.then(doc => {
				this.notifications_settings = doc;
				this.make();
			});
	}

	make() {
		this.dropdown = $('.navbar').find('.dropdown-notifications');
		this.dropdown_list = this.dropdown.find('.notifications-list');
		this.header_items = this.dropdown_list.find('.header-items');
		this.header_actions = this.dropdown_list.find('.header-actions');
		this.body = this.dropdown_list.find('.notification-list-body');
		this.reel = this.dropdown_list.find('.notifcation-reel')
		this.panel_events = this.dropdown_list.find('.panel-events');
		this.panel_notifications = this.dropdown_list.find('.panel-notifications');

		this.notification_indicator = this.dropdown.find(
			'.notifications-indicator'
		);

		this.user = frappe.session.user;

		this.setup_headers();
		let me = this;
		frappe.search.utils.make_function_searchable(
			me.route_to_settings,
			__('Notification Settings'),
		);

		// this.setup_notifications();
		this.setup_dropdown_events();
		// this.bind_events();
	}

	setup_headers() {
		// Add header actions
		$(`<span class="notification-settings pull-right" data-action="go_to_settings">
			${frappe.utils.icon('setting-gear')}
		</span>`)
			.on('click', (e) => this.go_to_settings(e))
			.appendTo(this.header_actions);

		$(`<span class="mark-all-read pull-right" data-action="mark_all_as_read">
			${frappe.utils.icon('mark-as-read')}
		</span>`)
			.on('click', (e) => this.mark_all_as_read(e))
			.appendTo(this.header_actions);

		this.categories = [
			{
				label: __("Notifications"),
				id: "notifications",
				view: NotificationsView,
				el: this.panel_notifications,
				transform: 'translateX(0%)'
			},
			{
				label: __("Today's Events"),
				id: "todays_events",
				view: EventsView,
				el: this.panel_events,
				transform: 'translateX(-50%)'
			}
		];

		let get_headers_html = (item) => {
			let active = item.id == "notifications" ? 'active' : ''

			let html = `<li class="notifications-category ${active}"
					id="${item.id}"
					data-toggle="collapse"
				>${item.label}</li>`;

			return html;
		};

		let navitem = $(`<ul class="notification-item-tabs nav nav-tabs" role="tablist"></ul>`);
		this.categories = this.categories.map(item => {
			item.dom = $(get_headers_html(item));
			item.dom.on('click', (e) => {
				e.stopImmediatePropagation();
				this.switch_tab(item);
			})
			navitem.append(item.dom);

			return item
		})
		navitem.appendTo(this.header_items);
		this.make_tab_view(this.categories[0]);
		this.make_tab_view(this.categories[1]);
	}

	switch_tab(item) {
		this.categories.forEach((item) => {
			item.dom.removeClass("active");
		});

		this.reel[0].style.transform = item.transform;

		item.dom.addClass("active");

		this.tabs[item.id]
		this.current_tab = this.tabs[item.id]
	}

	make_tab_view(item) {
		let tabView = new item.view(item.el);
		this.tabs[item.id] = tabView;
	}

	go_to_settings(e) {
		e.stopImmediatePropagation();
		this.dropdown.dropdown('hide');
		this.route_to_settings();
	}

	route_to_settings() {
		frappe.set_route(`#Form/Notification Settings/${frappe.session.user}`);
	}

	mark_all_as_read(e) {
		e.stopImmediatePropagation();
		this.dropdown_list.find('.unread').removeClass('unread');
		frappe.call(
			'frappe.desk.doctype.notification_log.notification_log.mark_all_as_read',
		);
	}

	change_activity_status() {
		if (this.dropdown_list.find('.activity-status')) {
			this.dropdown_list.find('.activity-status').replaceWith(
				`<a class="recent-item text-center text-muted"
					href="#List/Notification Log">
					<div class="full-log-btn">${__('View Full Log')}</div>
				</a>`
			);
		}
	}

	set_field_as_read(docname, $el) {
		frappe.call(
			'frappe.desk.doctype.notification_log.notification_log.mark_as_read',
			{ docname: docname }
		).then(() => {
			$el.removeClass('unread');
		});
	}

	explicitly_mark_as_read(e, $target) {
		e.preventDefault();
		e.stopImmediatePropagation();
		let docname = $target.parents('.unread').attr('data-name');
		this.set_field_as_read(docname, $target.parents('.unread'));
	}

	mark_as_read(e, $target) {
		let docname = $target.attr('data-name');
		let df = this.dropdown_items.filter(f => docname.includes(f.name))[0];
		this.set_field_as_read(df.name, $target);
	}

	toggle_seen(flag) {
		frappe.call(
			'frappe.desk.doctype.notification_settings.notification_settings.set_seen_value',
			{
				value: cint(flag),
				user: frappe.session.user
			}
		);
	}

	setup_dropdown_events() {
		this.dropdown.on('hide.bs.dropdown', e => {
			let hide = $(e.currentTarget).data('closable');
			$(e.currentTarget).data('closable', true);
			return hide;
		});

		this.dropdown.on('show.bs.dropdown', () => {
			this.toggle_seen(true);
			if (this.notification_indicator.is(':visible')) {
				this.notification_indicator.hide();
				frappe.call(
					'frappe.desk.doctype.notification_log.notification_log.trigger_indicator_hide'
				);
			}
		});

		this.dropdown.on('click', e => {
			$(e.currentTarget).data('closable', true);
		});
	}
};


frappe.ui.notifications = {
	get_notification_config() {
		return frappe.xcall('frappe.desk.notifications.get_notification_info').then(r => {
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
		let filters = frappe.ui.notifications.config['conditions'][doctype];
		if (filters && $.isPlainObject(filters)) {
			if (!frappe.route_options) {
				frappe.route_options = {};
			}
			$.extend(frappe.route_options, filters);
		}
		frappe.set_route('List', doctype);
	}
};

class BaseNotificaitonsView {
	constructor(wrapper) {
		// wrapper, max_length
		this.wrapper = wrapper;
		this.max_length = 20;
		this.container = $(`<div></div>`).appendTo(this.wrapper);
		this.make();
	}

	show() {
		this.container.show()
	}

	hide() {
		this.container.hide()
	}
}

class NotificationsView extends BaseNotificaitonsView {
	make() {
		this.setup_notification_listeners();
		this.get_notifications_list(this.max_length).then(list => {
			this.dropdown_items = list;
			this.render_notifications_dropdown();
		});
	}

	update_dropdown() {
		this.get_notifications_list(1).then(r => {
			let new_item = r[0];
			this.dropdown_items.unshift(new_item);
			if (this.dropdown_items.length > this.max_length) {
				this.dropdown_list
					.find('.recent-notification')
					.last()
					.remove();
				this.dropdown_items.pop();
			}

			this.insert_into_dropdown();
		});
	}

	insert_into_dropdown() {
		let new_item = this.dropdown_items[0];
		let new_item_html = this.get_dropdown_item_html(new_item);
		$(new_item_html).prependTo(this.container);
		this.change_activity_status();
	}

	get_dropdown_item_html(field) {
		let doc_link = this.get_item_link(field);

		let read_class = field.read ? '' : 'unread';
		let message = field.subject;

		let title = message.match(/<b class="subject-title">(.*?)<\/b>/);
		message = title ? message.replace(title[1], frappe.ellipsis(strip_html(title[1]), 100)) : message;

		let timestamp = frappe.datetime.comment_when(field.creation);
		let message_html = `<div class="message">
			<div>${message}</div>
			<div class="notification-timestamp text-muted">
				${timestamp}
			</div>
		</div>`;

		let user = field.from_user;
		let user_avatar = frappe.avatar(user, 'avatar-medium user-avatar');

		let item_html =
			`<a class="recent-item notification-item ${read_class}"
				href="${doc_link}"
				data-name="${field.name}"
			>
				<div class="notification-body">
					${user_avatar}
					${message_html}
				</div>
				<div class="mark-as-read">
				</div>
			</a>`;

		return item_html;
	}

	render_notifications_dropdown() {
		let body_html = '';
		let view_full_log_html = '';
		let dropdown_html;

		if (this.notifications_settings && !this.notifications_settings.enabled) {
			dropdown_html = `<li class="recent-item notification-item">
				<span class="text-muted">
					${__('Notifications Disabled')}
				</span></li>`;
		} else {
			if (this.dropdown_items.length) {
				this.dropdown_items.forEach(field => {
					let item_html = this.get_dropdown_item_html(field);
					if (item_html) body_html += item_html;
				});
				view_full_log_html = `<a class="list-footer"
					href="#List/Notification Log">
						<div class="full-log-btn">${__('See all Activity')}</div>
					</a>`;
			} else {
				body_html += `<li class="recent-item text-center activity-status">
					<span class="text-muted">
						${__('No activity')}
					</span></li>`;
			}
			dropdown_html = body_html + view_full_log_html;
		}

		this.container.html(dropdown_html);
	}

	get_notifications_list(limit) {
		return frappe.db.get_list('Notification Log', {
			fields: ['*'],
			limit: limit,
			order_by: 'creation desc'
		});
	}

	get_item_link(notification_doc) {
		const link_doctype =
			notification_doc.type == 'Alert' ? 'Notification Log' : notification_doc.document_type;
		const link_docname =
			notification_doc.type == 'Alert' ? notification_doc.name : notification_doc.document_name;
		return frappe.utils.get_form_link(
			link_doctype,
			link_docname
		);
	}

	setup_notification_listeners() {
		// REDESIGN-TODO: toggle icon indicator
		frappe.realtime.on('notification', () => {
			// this.dropdown.find('.notifications-indicator').show();
			this.update_dropdown();
		});

		frappe.realtime.on('indicator_hide', () => {
			// this.dropdown.find('.notifications-indicator').hide();
		});
	}
}

class EventsView extends BaseNotificaitonsView {
	make() {
		let today = frappe.datetime.get_today();
		frappe.xcall('frappe.desk.doctype.event.event.get_events', {
			start: today,
			end: today
		}).then(event_list => {
			this.render_events_html(event_list);
		});
	}

	render_events_html(event_list) {
		let html = '';
		if (event_list.length) {
			let get_event_html = (event) => {
				let time = __("All Day");
				if (!event.all_day) {
					let start_time = frappe.datetime.get_time(event.starts_on);
					let days_diff = frappe.datetime.get_day_diff(event.ends_on, event.starts_on)
					let end_time = frappe.datetime.get_time(event.ends_on);
					if (days_diff > 1) {
						end_time = __("Rest of the day");
					}
					time = `${start_time} - ${end_time}`;
				}

				// REDESIGN-TODO: Add Participants to get_events query
				let particpants = '';
				if (event.particpants) {
					particpants = frappe.avatar_group(event.particpants, 3)
				}

				// REDESIGN-TODO: Add location to calendar field
				let location = '';
				if (event.location) {
					location = `, ${event.location}`;
				}

				return `<a class="recent-item event" href="#Form/Event/${event.name}">
					<div class="event-border" style="border-color: ${event.color}"></div>
					<div class="event-item">
						<div class="event-subject">${event.subject}</div>
						<div class="event-time">${time}${location}</div>
						${particpants}
					</div>
				</a>`;
			};
			html = event_list.map(get_event_html).join('');
		} else {
			html = `<li class="recent-item text-center">
					<span class="text-muted">${__('No Events Today')}</span>
				</li>`;
		}

		this.container.html(html);
	}
}