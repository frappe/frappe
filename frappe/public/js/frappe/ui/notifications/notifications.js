
frappe.ui.Notifications = class Notifications {

	constructor() {
		this.$dropdown = $('.navbar').find('.dropdown-notifications');
		this.$dropdown_list = this.$dropdown.find('.notifications-list');
		this.$notification_indicator = this.$dropdown.find('.notifications-indicator');
		this.user = frappe.session.user;
		this.max_length = 20;

		this.categories = ['Notifications', 'Upcoming Events', 'Open Documents'];
		this.render_dropdown_headers();
		this.$notifications = this.$dropdown_list.find('#notifications');
		this.$open_docs = this.$dropdown_list.find('#open-documents');
		this.$upcoming_events = this.$dropdown_list.find('#upcoming-events');

		this.setup_notification_settings();
		this.setup_notifications();
		this.setup_upcoming_events();
		this.setup_open_document_count();
		this.bind_events();
	}

	setup_notifications() {
		this.get_notifications_list(this.max_length).then(list => {
			this.dropdown_items = list;
			this.render_notifications_dropdown();
			this.setup_view_full_log();

			if (this.$notifications.find('.unseen').length) {
				this.$notification_indicator.show();
			}
		});
	}

	setup_upcoming_events() {
		this.$dropdown_list.on('click', '.upcoming-events-header', (e) => {
			let hide = $(e.currentTarget).next().hasClass("in");
			if (!hide) {
				let today = frappe.datetime.now_date();

				frappe.xcall('frappe.desk.doctype.event.event.get_events', {
					start: today,
					end: frappe.datetime.add_days(today, 3)
				}).then((event_list) => {
					this.render_events_html(event_list);
				});
			}
		});
	}

	render_events_html(event_list) {
		let html = '';
		if (event_list.length) {
			let get_event_html = (event) => {
				let time = frappe.datetime.get_time(event.starts_on);
				return `<a class="recent-item event" href="#Form/Event/${event.name}">
					<span class="event-time bold">${time}</span>
					<span class="event-subject"> ${event.subject}</span>
				</a>`;
			};
			html = event_list.map(get_event_html).join('');
		} else {
			html = `<li class="recent-item text-center">
					<span class="text-muted">${__('No Upcoming Events')}</span>
				</li>`;
		}

		this.$upcoming_events.html(html);
	}

	setup_open_document_count() {
		this.open_docs_config =  {
			'ToDo': { label: __('To Do') },
			'Event': { label: __('Calendar'), route: 'List/Event/Calendar' },
		};

		this.$dropdown_list.on('click', '.open-documents-header', (e) => {
			let hide = $(e.currentTarget).next().hasClass('in');
			if (!hide) {
				frappe.xcall('frappe.desk.notifications.get_notification_info').then((r) => {
					this.open_document_list = r;
					this.render_open_document_count();
				});
			}
		});

		this.setup_open_docs_route();
	}

	render_open_document_count() {
		this.$open_docs.html('');
		let defaults = ['ToDo'];
		this.get_counts(this.open_document_list['open_count_doctype'], 1, defaults);
		let targets = { doctypes: {} }, map = this.open_document_list['targets'];

		Object.keys(map).map(doctype => {
			Object.keys(map[doctype]).map(doc => {
				targets[doc] = map[doctype][doc];
				targets.doctypes[doc] = doctype;
			});
		});

		this.get_counts(targets, 1, null, ['doctypes'], true);
		this.get_counts(this.open_document_list['open_count_doctype'],
			0, null, defaults);
	}

	get_counts(map, divide, keys, excluded = [], target = false) {
		let empty_map = 1;
		keys = keys ? keys
			: Object.keys(map).sort().filter(e => !excluded.includes(e));
		keys.map(key => {
			let doc_dt = (map.doctypes) ? map.doctypes[key] : undefined;
			if (map[key] > 0 || target) {
				this.add_notification_html(key, map[key], doc_dt, target);
				empty_map = 0;
			}
		});

		if (divide && !empty_map) {
			this.$open_docs.append($('<li class="divider"></li>'));
		}
	}

	add_notification_html(name, value, doc_dt, target = false) {
		let label = this.open_docs_config[name] ?
			this.open_docs_config[name].label :
			name;
		let title = target ? `title="Your Target"` : '';
		let $list_item = !target
			? $(`<li><a class="badge-hover" href="#" onclick="return false;" data-doctype="${name}" ${title}>
				${__(label)}
				<span class="badge pull-right">${value}</span>
			</a></li>`)
			: $(`<li><a class="progress-small" href="#" onclick="return false;" ${title}
				data-doctype="${doc_dt}" data-doc="${name}">
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

	show_open_count_list(doctype) {
		let filters = this.open_document_list['conditions'][doctype];
		if (filters && $.isPlainObject(filters)) {
			if (!frappe.route_options) {
				frappe.route_options = {};
			}
			$.extend(frappe.route_options, filters);
		}
		frappe.set_route("List", doctype);
	}

	setup_open_docs_route() {

		this.$open_docs.on('click', 'li a', (e) => {
			let doctype = $(e.currentTarget).attr('data-doctype');
			let doc = $(e.currentTarget).attr('data-doc');
			if (!doc) {
				let config = this.open_docs_config[doctype] || {};
				if (config.route) {
					frappe.set_route(config.route);
				} else if (config.click) {
					config.click();
				} else {
					this.show_open_count_list(doctype);
				}
			} else {
				frappe.set_route("Form", doctype, doc);
			}
		});
	}

	update_dropdown() {
		this.get_notifications_list(1).then(r => {
			let new_item = r[0];
			this.dropdown_items.unshift(new_item);
			if (this.dropdown_items.length > this.max_length) {
				this.$dropdown_list.find('.recent-notification').last().remove();
				this.dropdown_items.pop();
			}

			this.insert_into_dropdown();
		});
	}

	insert_into_dropdown() {
		let new_item = this.dropdown_items[0];
		let new_item_html = this.get_dropdown_item_html(new_item);
		$(new_item_html).prependTo(this.$dropdown_list.find('#notifications'));
		this.change_activity_status();
	}

	change_activity_status() {
		if (this.$dropdown_list.find('.activity-status')) {
			this.$dropdown_list.find('.activity-status').replaceWith(
				`<a class="recent-item text-center text-muted full-log-btn" 
					href="#List/Notification Log">
					${__('View Full Log')}
				</a>`);
		}
	}

	check_seen() {
		let unseen_logs = this.dropdown_items.filter(item => item.seen === 0);
		frappe.call(
			'frappe.core.doctype.notification_log.notification_log.set_notification_as_seen', 
			{notification_log: unseen_logs}
		);
	}

	get_notifications_list(limit) {
		return frappe.db.get_list('Notification Log', {
			fields: ['*'],
			limit: limit,
			order_by: 'creation desc'
		}).then((notifications_list) => {
			return notifications_list;
		});
	}

	render_notifications_dropdown() {
		let body_html = '';
		let view_full_log_html = '';
		let dropdown_html;

		if (!frappe.boot.notifications_enabled) {
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
				view_full_log_html = `<a class="recent-item text-center text-muted full-log-btn">
						${__('View Full Log')}
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
		let doc_link = frappe.utils.get_form_link(field.document_type, field.document_name);
		let seen_class = field.seen? '': 'unseen';
		let message = field.subject;
		let message_html = `<div class="message">${message}</div>`;
		let user = field.from_user;
		let user_avatar = frappe.avatar(user, 'avatar-small user-avatar');
		let timestamp = frappe.datetime.comment_when(field.creation, true);
		let item_html = `<a class="recent-item ${seen_class}" href = "${doc_link}">
				${user_avatar}
				${message_html}
				<div class="notification-timestamp text-muted">
					${timestamp}
				</div>
		</a>`;

		return item_html;
	}


	setup_view_full_log() {
		this.$dropdown_list.find('.full-log-btn').on('click', () => {
			frappe.set_route('List', 'Notification Log');
		});
	}


	render_dropdown_headers() {
		let get_headers_html = (category) => {
			let category_id = frappe.scrub(category, '-');
			let category_header_class = frappe.scrub(category, '-') + '-header';
			let settings_html = category === 'Notifications'?
				`<span class="notification-settings pull-right">${__('Settings')}</span>`
				: '';
			let html = 
				`<li class="notifications-category">
					<li class="text-muted header ${category_header_class}" 
						href="#${category_id}" 
						data-toggle="collapse">
						${category}
						<span class="octicon octicon-chevron-down collapse-indicator"></span>
						${settings_html}
					</li>
					<div id = "${category_id}" class="collapse category-list">
						<div class="text-center text-muted notifications-loading">
							${__('Loading...')}
						</div>
					</div>
				</li>`;

			return html;
		};

		let html = this.categories.map(get_headers_html).join('<li class="divider"></li>');
		this.$dropdown_list.append(html);
		this.$dropdown_list.find('#notifications').collapse('show');
		this.toggle_collapse_indicator(this.$dropdown_list.find('#notifications'));
	}

	setup_notification_settings() {

		this.$dropdown_list.find('.notification-settings').on('click', (e) => {
			e.preventDefault();
			frappe.db.exists('Notification Settings', frappe.session.user).then((exists)=> {
				if (!exists) {
					frappe.call(
						'frappe.core.doctype.notification_settings.notification_settings.create_notification_settings',
					).then(() => {
						frappe.set_route(`#Form/Notification Settings/${frappe.session.user}`);
					});
				} else {
					frappe.set_route(`#Form/Notification Settings/${frappe.session.user}`);
				}
			});
		});
	}

	bind_events() {
		this.setup_notification_listener();
		this.setup_dropdown_events();
	
		this.$dropdown_list.on('click', '.recent-item', () => {
			this.$dropdown.removeClass('open');
		});

		$('.category-list').on('hide.bs.collapse', (e) => {
			this.toggle_collapse_indicator($(e.currentTarget));
		});

		$('.category-list').on('show.bs.collapse', (e) => {
			this.toggle_collapse_indicator($(e.currentTarget));
		});
	}

	setup_notification_listener() {
		frappe.realtime.on('notification', () => {
			this.$dropdown.find('.notifications-indicator').show();
			this.update_dropdown();
		});
	}

	setup_dropdown_events() {
		this.$dropdown_list.find('#upcoming-events, #open-documents, #notifications').collapse({
			toggle: false
		});
		this.$dropdown.on('hide.bs.dropdown', (e) => {
			this.$notification_indicator.hide();
			let hide = $(e.currentTarget).data('closable');
			if (hide) {
				this.$dropdown_list.find('#notifications').collapse('show');
				this.$dropdown_list.find('#upcoming-events, #open-documents').collapse('hide');
			}
			this.$dropdown_list.find('.unseen').removeClass('unseen');
			$(e.currentTarget).data('closable', true);
			return hide;
		});

		this.$dropdown.on('show.bs.dropdown', () => {
			this.check_seen();
		});

		this.$dropdown.on('click', (e) => {
			if ($(e.target).closest('.dropdown-toggle').length) {
				$(e.currentTarget).data('closable', true);
			} else {
				$(e.currentTarget).data('closable', false);
			}
		});
	}

	toggle_collapse_indicator($el) {
		$el.prev().find('.collapse-indicator').toggleClass("octicon-chevron-down");
		$el.prev().find('.collapse-indicator').toggleClass("octicon-chevron-up");
	}

};
