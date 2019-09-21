
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
				return `<li class="recent-item event">
					<a href="#Form/Event/${event.name}">
						<span class="event-time bold">${time}</span>
						<span class="event-subject"> ${event.subject}</span>
					</a>
				</li>`;
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
		let me = this;

		this.$open_docs.on('click', 'li a', function() {
			let doctype = $(this).attr('data-doctype');
			let doc = $(this).attr('data-doc');
			if (!doc) {
				let config = me.open_docs_config[doctype] || {};
				if (config.route) {
					frappe.set_route(config.route);
				} else if (config.click) {
					config.click();
				} else {
					me.show_open_count_list(doctype);
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

		if (this.dropdown_items.length) {
			this.dropdown_items.forEach(field => {
				let item_html = this.get_dropdown_item_html(field);
				if (item_html) body_html += item_html;
			});
			view_full_log_html = `<li class="recent-item text-center">
				<a class="text-muted full-log-btn">
					${__('View Full Log')}
				</a></li>`;
		} else {
			body_html += `<li class="recent-item text-center">
				<a href="#" onclick = "return false" class="text-muted">
					${__('No activity')}
				</a></li>`;
		}

		let dropdown_html = body_html + view_full_log_html;
		this.$notifications.html(dropdown_html);
	}

	get_dropdown_item_html(field) {
		let doc_link = frappe.utils.get_form_link(field.reference_doctype, field.reference_name);
		let seen_class = field.seen? '': 'unseen';
		let message = field.subject;
		let message_html = `<div class="message">${message}</div>`;
		let user = field.reference_user;
		let user_avatar = frappe.avatar(user, 'avatar-small user-avatar');
		let timestamp = frappe.datetime.comment_when(field.creation, true);
		let item_html = `<li class="recent-item ${seen_class}">
			${user_avatar}
			<a class= "message-link" href = "${doc_link}">
				${message_html}
				<div class="notification-timestamp text-muted">
					${timestamp}
				</div>
			</a>
		</li>`;

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
					<div id = "${category_id}" class="collapse">
						<div class="text-center text-muted notifications-loading">
							${__('Loading...')}
						</div>
					</div>
				</li>`;

			return html;
		};

		let html = this.categories.map(get_headers_html).join('<li class="divider"></li>');
		this.$dropdown_list.append(html);
	}

	setup_notification_settings() {

		this.$dropdown_list.find('.notification-settings').on('click', (e) => {
			e.preventDefault();
			frappe.db.exists('Notification Settings', frappe.session.user).then((exists)=> {
				if(!exists) {
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
		let me = this;

		frappe.realtime.on('notification', () => {
			this.$dropdown.find('.notifications-indicator').show();
			this.update_dropdown();
		});

		this.$dropdown.on('hide.bs.dropdown', function() {
			me.$notification_indicator.hide();
			let hide = $(this).data('closable');
			me.$dropdown_list.find('.unseen').removeClass('unseen');
			$(this).data('closable', true);
			return hide;
		});

		this.$dropdown.on('show.bs.dropdown', () => {
			this.check_seen();
			this.$dropdown_list.find('#notifications').collapse('show');
		});

		this.$dropdown.on('click', function(e) {
			if ($(e.target).closest('.dropdown-toggle').length) {
				$(this).data('closable', true);
			} else {
				$(this).data('closable', false);
			}
		});

		this.$dropdown_list.on('click', '.recent-item', () => {
			this.$dropdown.removeClass('open');
		});

		this.$dropdown.find('.header').on('click', function() {
			let hide = $(this).next().hasClass("in");
			$(this).find('.collapse-indicator').toggleClass("octicon-chevron-down", hide);
			$(this).find('.collapse-indicator').toggleClass("octicon-chevron-up", !hide);
		});
	}

};
