frappe.provide('frappe.search');

frappe.ui.Notifications = class Notifications {
	constructor() {
		frappe.model
			.with_doc('Notification Settings', frappe.session.user)
			.then(doc => {
				this.notifications_settings = doc;
				this.make();
			});
	}

	make() {
		this.$dropdown = $('.navbar').find('.dropdown-notifications');
		this.$dropdown_list = this.$dropdown.find('.notifications-list');
		this.$notification_indicator = this.$dropdown.find(
			'.notifications-indicator'
		);
		this.user = frappe.session.user;
		this.max_length = 20;

		this.render_dropdown_headers();
		this.$notifications = this.$dropdown_list.find(
			'.category-list[data-category="Notifications"]'
		);
		this.$open_docs = this.$dropdown_list.find(
			'.category-list[data-category="Open Documents"]'
		);
		this.$today_events = this.$dropdown_list.find(
			'.category-list[data-category="Todays Events"]'
		);

		frappe.utils.bind_actions_with_object(this.$dropdown_list, this);
		let me = this;
		frappe.search.utils.make_function_searchable(
			me.route_to_settings,
			__('Notification Settings'),
		);

		this.setup_notifications();
		this.bind_events();
	}

	route_to_settings() {
		frappe.set_route(`#Form/Notification Settings/${frappe.session.user}`);
	}

	setup_notifications() {
		this.get_notifications_list(this.max_length).then(list => {
			this.dropdown_items = list;
			this.render_notifications_dropdown();
			if (this.notifications_settings.seen == 0) {
				this.$notification_indicator.show();
			}
		});
	}

	render_todays_events(e, $target) {
		let hide = $target.next().hasClass('in');
		if (!hide) {
			let today = frappe.datetime.get_today();
			frappe.xcall('frappe.desk.doctype.event.event.get_events', {
				start: today,
				end: today
			}).then(event_list => {
				this.render_events_html(event_list);
			});
		}
	}

	render_events_html(event_list) {
		let html = '';
		if (event_list.length) {
			let get_event_html = event => {
				let time = frappe.datetime.get_time(event.starts_on);
				return `<a class="recent-item event" href="#Form/Event/${event.name}">
					<span class="event-time bold">${time}</span>
					<span class="event-subject">${event.subject}</span>
				</a>`;
			};
			html = event_list.map(get_event_html).join('');
		} else {
			html = `<li class="recent-item text-center">
					<span class="text-muted">${__('No Events Today')}</span>
				</li>`;
		}

		this.$today_events.html(html);
	}

	get_open_document_config(e) {
		this.open_docs_config = {
			ToDo: { label: __('To Do') },
			Event: { label: __('Calendar'), route: 'List/Event/Calendar' }
		};

		let hide = $(e.currentTarget)
			.next()
			.hasClass('in');
		if (!hide) {
			frappe.ui.notifications.get_notification_config().then(r => {
				this.open_document_list = r;
				this.render_open_document_count();
			});
		}
	}

	render_open_document_count() {
		this.$open_docs.html('');
		let defaults = ['ToDo'];
		this.get_counts(this.open_document_list['open_count_doctype'], 1, defaults);
		let targets = { doctypes: {} },
			map = this.open_document_list['targets'];

		Object.keys(map).map(doctype => {
			Object.keys(map[doctype]).map(doc => {
				targets[doc] = map[doctype][doc];
				targets.doctypes[doc] = doctype;
			});
		});

		this.get_counts(targets, 1, null, ['doctypes'], true);
		this.get_counts(
			this.open_document_list['open_count_doctype'],
			0,
			null,
			defaults
		);
	}

	get_counts(map, divide, keys, excluded = [], target = false) {
		let empty_map = 1;
		keys = keys
			? keys
			: Object.keys(map).sort().filter(e => !excluded.includes(e));
		keys.map(key => {
			let doc_dt = map.doctypes ? map.doctypes[key] : undefined;
			if (map[key] > 0 || target) {
				this.add_open_document_html(key, map[key], doc_dt, target);
				empty_map = 0;
			}
		});

		if (divide && !empty_map) {
			this.$open_docs.append($('<li class="divider"></li>'));
		}
	}

	add_open_document_html(name, value, doc_dt, target = false) {
		let label = this.open_docs_config[name]
			? this.open_docs_config[name].label
			: name;
		let title = target ? `title="${__('Your Target')}"` : '';
		let $list_item = !target
			? $(`<li><a class="badge-hover" data-action="route_to_document_type" data-doctype="${name}" ${title}>
				${__(label)}
				<span class="badge pull-right">${value}</span>
			</a></li>`)
			: $(`<li><a class="progress-small" data-action="route_to_document_type" ${title}
				data-doctype="${doc_dt}" data-docname="${name}">
					<span class="dropdown-item-label">${__(label)}<span>
					<div class="progress-chart">
						<div class="progress">
							<div class="progress-bar" style="width: ${value}%"></div>
						</div>
					</div>
			</a></li>`);

		this.$open_docs.append($list_item);
		if (!target) this.total += value;
	}

	route_to_document_type(e) {
		this.$dropdown.removeClass('open');
		this.$dropdown.trigger('hide.bs.dropdown');
		let doctype = $(e.currentTarget).attr('data-doctype');
		let docname = $(e.currentTarget).attr('data-docname');
		if (!docname) {
			let config = this.open_docs_config[doctype] || {};
			if (config.route) {
				frappe.set_route(config.route);
			} else if (config.click) {
				config.click();
			} else {
				frappe.ui.notifications.show_open_count_list(doctype);
			}
		} else {
			frappe.set_route('Form', doctype, docname);
		}
	}

	update_dropdown() {
		this.get_notifications_list(1).then(r => {
			let new_item = r[0];
			this.dropdown_items.unshift(new_item);
			if (this.dropdown_items.length > this.max_length) {
				this.$dropdown_list
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
		$(new_item_html).prependTo(this.$dropdown_list.find(this.$notifications));
		this.change_activity_status();
	}

	change_activity_status() {
		if (this.$dropdown_list.find('.activity-status')) {
			this.$dropdown_list.find('.activity-status').replaceWith(
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
		).then(()=> {
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

	mark_all_as_read(e) {
		e.stopImmediatePropagation();
		this.$dropdown_list.find('.unread').removeClass('unread');
		frappe.call(
			'frappe.desk.doctype.notification_log.notification_log.mark_all_as_read',
		);
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

	get_notifications_list(limit) {
		return frappe.db.get_list('Notification Log', {
			fields: ['*'],
			limit: limit,
			order_by: 'creation desc'
		});
	}

	render_notifications_dropdown() {
		let body_html = '';
		let view_full_log_html = '';
		let dropdown_html;

		if (this.notifications_settings && !this.notifications_settings.enabled) {
			dropdown_html = `<li class="recent-item text-center">
				<span class="text-muted">
					${__('Notifications Disabled')}
				</span></li>`;
		} else {
			if (this.dropdown_items.length) {
				this.dropdown_items.forEach(field => {
					let item_html = this.get_dropdown_item_html(field);
					if (item_html) body_html += item_html;
				});
				view_full_log_html = `<a class="recent-item text-center text-muted"
					href="#List/Notification Log">
						<div class="full-log-btn">${__('View Full Log')}</div>
					</a>`;
			} else {
				body_html += `<li class="recent-item text-center activity-status">
					<span class="text-muted">
						${__('No activity')}
					</span></li>`;
			}
			dropdown_html = body_html + view_full_log_html;
		}

		this.$notifications.html(dropdown_html);
	}

	get_dropdown_item_html(field) {
		let doc_link = this.get_item_link(field);
		let read_class = field.read ? '' : 'unread';
		let mark_read_action = field.read ? '': 'data-action="mark_as_read"';
		let message = field.subject;
		let title = message.match(/<b class="subject-title">(.*?)<\/b>/);
		message = title ? message.replace(title[1], frappe.ellipsis(title[1], 100)): message;
		let message_html = `<div class="message">${message}</div>`;
		let user = field.from_user;
		let user_avatar = frappe.avatar(user, 'avatar-small user-avatar');
		let timestamp = frappe.datetime.comment_when(field.creation, true);
		let item_html =
			`<a class="recent-item ${read_class}"
				href="${doc_link}"
				data-name="${field.name}"
				${mark_read_action}
			>
				${user_avatar}
				${message_html}
				<div class="notification-timestamp text-muted">
					${timestamp}
				</div>
				<span class="mark-read text-muted hidden-xs" data-action="explicitly_mark_as_read">
					${__('Mark as Read')}
				</span>
			</a>`;

		return item_html;
	}

	get_item_link(notification_doc) {
		const link_doctype =
			notification_doc.type == 'Alert' ? 'Notification Log': notification_doc.document_type;
		const link_docname =
			notification_doc.type == 'Alert' ? notification_doc.name: notification_doc.document_name;
		return frappe.utils.get_form_link(
			link_doctype,
			link_docname
		);
	}

	render_dropdown_headers() {
		this.categories = [
			{
				label: __("Notifications"),
				value: "Notifications"
			},
			{
				label: __("Today's Events"),
				value: "Todays Events",
				action: "render_todays_events"
			},
			{
				label: __("Open Documents"),
				value: "Open Documents",
				action: "get_open_document_config"
			}
		];

		let get_headers_html = category => {
			let category_id = frappe.dom.get_unique_id();
			let settings_html =
				category.value === 'Notifications'
					? `<span class="notification-settings pull-right" data-action="go_to_settings">
						${__('Settings')}
					</span>`
					: '';
			let mark_all_read_html =
				category.value === 'Notifications'
					? `<span class="mark-all-read pull-right" data-action="mark_all_as_read">
						${__('Mark all as Read')}
					</span>`
					: '';
			let html = `<li class="notifications-category">
					<li class="text-muted header"
						data-action="${category.action}"
						href="#${category_id}"
						data-toggle="collapse">
						${category.label}
						<span class="octicon octicon-chevron-down collapse-indicator"></span>
						${settings_html}
						${mark_all_read_html}
					</li>
					<div id="${category_id}" class="collapse category-list" data-category="${category.value}">
						<div class="text-center text-muted notifications-loading">
							${__('Loading...')}
						</div>
					</div>
				</li>`;

			return html;
		};

		let html = this.categories
			.map(get_headers_html)
			.join('<li class="divider"></li>');
		this.$dropdown_list.append(html);
		this.$dropdown_list
			.find('.category-list[data-category="Notifications"]')
			.collapse('show');
		this.toggle_collapse_indicator(
			this.$dropdown_list.find('.category-list[data-category="Notifications"]')
		);
	}

	go_to_settings(e) {
		e.stopImmediatePropagation();
		this.$dropdown.removeClass('open');
		this.$dropdown.trigger('hide.bs.dropdown');
		this.route_to_settings();
	}

	bind_events() {
		this.setup_dropdown_events();
		this.setup_notification_listeners();

		this.$dropdown_list.on('click', '.recent-item', () => {
			this.$dropdown.removeClass('open');
		});

		$('.category-list').on('hide.bs.collapse', e => {
			this.toggle_collapse_indicator($(e.currentTarget));
		});

		$('.category-list').on('show.bs.collapse', e => {
			this.toggle_collapse_indicator($(e.currentTarget));
		});
	}

	setup_notification_listeners() {
		frappe.realtime.on('notification', () => {
			this.$dropdown.find('.notifications-indicator').show();
			this.update_dropdown();
		});

		frappe.realtime.on('indicator_hide', () => {
			this.$dropdown.find('.notifications-indicator').hide();
		});
	}

	setup_dropdown_events() {
		this.$dropdown_list
			.find(
				'[data-category="Notifications"], [data-category="Todays Events"], [data-category="Open Documents"]'
			)
			.collapse({
				toggle: false
			});
		this.$dropdown.on('hide.bs.dropdown', e => {
			let hide = $(e.currentTarget).data('closable');
			$(e.currentTarget).data('closable', true);
			return hide;
		});

		this.$dropdown.on('show.bs.dropdown', () => {
			this.toggle_seen(true);
			if (this.$notification_indicator.is(':visible')) {
				this.$notification_indicator.hide();
				frappe.call(
					'frappe.desk.doctype.notification_log.notification_log.trigger_indicator_hide'
				);
			}
		});

		this.$dropdown.on('click', e => {
			if ($(e.target).closest('.dropdown-toggle').length) {
				$(e.currentTarget).data('closable', true);
			} else {
				$(e.currentTarget).data('closable', false);
			}
		});
	}

	toggle_collapse_indicator($el) {
		$el
			.prev()
			.find('.collapse-indicator')
			.toggleClass('octicon-chevron-down');
		$el
			.prev()
			.find('.collapse-indicator')
			.toggleClass('octicon-chevron-up');
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
			this.get_notification_config().then(()=> {
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
