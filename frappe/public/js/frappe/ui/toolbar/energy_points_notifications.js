
frappe.ui.EnergyPointsNotifications = class {

	constructor() {
		this.$dropdown = $('.navbar').find('.dropdown-energy-points');
		this.$dropdown_list = this.$dropdown.find('.recent-points-list');
		this.$notification_indicator = this.$dropdown.find('.energy-points-notification');
		this.max_length = 20;
		this.setup_energy_points_notifications();
	}

	setup_energy_points_notifications() {
		this.get_energy_points_list(this.max_length).then(user_points_list => {
			this.dropdown_items = user_points_list;
			this.render_energy_points_dropdown();
			this.setup_view_full_log();
			if (this.$dropdown_list.find('.unseen').length) {
				this.$notification_indicator.show();
			}
		});

		this.bind_events();
	}

	bind_events() {
		frappe.realtime.on('energy_points_notification', () => {
			this.$dropdown.find('.energy-points-notification').show();
			this.update_dropdown();
		});

		this.$dropdown.on('hide.bs.dropdown', () => {
			this.$notification_indicator.hide();
			this.$dropdown_list.find('.unseen').removeClass('unseen');
		});

		this.$dropdown.on('show.bs.dropdown', () => {
			this.check_seen();
		});
	}

	update_dropdown() {
		this.get_energy_points_list(1).then(r => {
			let new_item = r[0];
			this.dropdown_items.unshift(new_item);
			if (this.dropdown_items.length > this.max_length) {
				this.$dropdown_list.find('.recent-points-item').last().remove();
				this.dropdown_items.pop();
			}
			this.insert_into_dropdown();
		});
	}

	insert_into_dropdown() {
		let new_item = this.dropdown_items[0];
		let new_item_html = this.get_dropdown_item_html(new_item);
		let new_item_date_range = this.get_date_range_title(new_item.creation);
		let current_date_range = this.get_date_range_title(this.dropdown_items[1].creation);
		if (current_date_range !== new_item_date_range) {
			let $date_range = $(`<li class="points-date-range text-muted">${new_item_date_range}</li>`);
			$date_range.insertAfter(this.$dropdown_list.find('.points-updates-header'));
			$(new_item_html).insertAfter($date_range);
		} else {
			$(new_item_html).insertAfter(this.$dropdown_list.find('.points-date-range').eq(0));
		}
	}

	check_seen() {
		let unseen_logs = this.dropdown_items.filter(item => item.seen === 0);
		frappe.call('frappe.social.doctype.energy_point_log.energy_point_log.set_notification_as_seen', {point_logs: unseen_logs});
	}

	get_date_range_title(date) {
		let current_date = frappe.datetime.now_date();
		let prev_week = frappe.datetime.add_days(current_date, -7);
		let prev_month = frappe.datetime.add_months(frappe.datetime.now_date(), -1);
		if (date >= current_date) {
			return __('Today');
		} else if (date > prev_week) {
			return __('Last 7 days');
		} else if (date > prev_month) {
			return __('Last 30 days');
		} else  {
			return __('Older');
		}
	}

	get_energy_points_list(limit) {
		return frappe.db.get_list('Energy Point Log', {
			filters: {
				user: frappe.session.user,
				type: ['not in', ['Review']],
			},
			fields:
				['name', 'user', 'points', 'reference_doctype', 'reference_name', 'reason', 'type', 'seen', 'rule', 'owner', 'creation'],
			limit: limit,
			order_by: 'creation desc'
		}).then((energy_points_list) => {
			return energy_points_list;
		});
	}

	render_energy_points_dropdown() {
		let header_html =
			`<li class="points-updates-header">
				<span class="points-updates-title bold text-muted">${__('Energy Points')}</span>
				<a href="#social/users" class="points-leaderboard text-muted hidden-xs">${__('Leaderboard')}</a>
			</li>`;
		let body_html = '';
		let view_full_log_html = '';

		if (this.dropdown_items.length) {
			let date_range = this.get_date_range_title(this.dropdown_items[0].creation);
			body_html += `<li class="points-date-range text-muted">${date_range}</li>`;
			this.dropdown_items.forEach(field => {
				let current_field_date_range = this.get_date_range_title(field.creation);
				if (date_range !== current_field_date_range) {
					body_html += `<li class="points-date-range text-muted">${current_field_date_range}</li>`;
					date_range = current_field_date_range;
				}
				let item_html = this.get_dropdown_item_html(field);
				if (item_html) body_html += item_html;
			});
			view_full_log_html = `<li><a class="text-muted text-center full-log-btn">${__('View Full Log')}</a></li>`;
		} else {
			body_html += `<li><a href="#" onclick = "return false" class="text-muted text-center">${__('No activity')}</a></li>`;
		}
		let dropdown_html = header_html + body_html + view_full_log_html;
		this.$dropdown_list.html(dropdown_html);
	}

	get_dropdown_item_html(field) {
		let doc_link = frappe.utils.get_form_link(field.reference_doctype, field.reference_name);
		let link_html_string = field.seen ? `<a href=${doc_link}>`: `<a href=${doc_link} class="unseen">`;
		let points_html = `<div class="points-update">${frappe.energy_points.get_points(field.points)}</div>`;
		let message_html = this.get_message_html(field);

		let item_html = `<li class="recent-points-item">
			${link_html_string}
			${points_html}
			<div class="points-reason">
				${message_html}
			</div>
			</a>
		</li>`;
		return item_html;
	}

	get_message_html(field) {
		let owner_name = frappe.user.full_name(field.owner).trim();
		owner_name = frappe.ellipsis(owner_name, 50);
		let message_html = '';
		let reference_doc = `
			<span class="points-reason-name text-muted">
					${field.reference_name}
			</span>
		`;
		let reason_string = `
			<span class="hidden-xs">
				- "${frappe.ellipsis(field.reason, 50)}"
			</span>
		`;
		if (field.type === 'Auto' ) {
			message_html = __('For {0} {1}',
				[field.rule, reference_doc]);
		} else {
			if (field.type === 'Appreciation') {
				message_html = __('{0} appreciated your work on {1} {2}',
					[owner_name, reference_doc, reason_string]);
			} else if (field.type === 'Criticism') {
				message_html = __('{0} criticized your work on {1} {2}',
					[owner_name, reference_doc, reason_string]);
			} else if (field.type === 'Revert') {
				message_html = __('{0} reverted your points on {1} {2}',
					[owner_name, reference_doc, reason_string]);
			}
		}
		return message_html;
	}

	setup_view_full_log() {
		this.$dropdown_list.find('.full-log-btn').on('click', () => {
			frappe.set_route('List', 'Energy Point Log', {user: frappe.session.user});
		});
	}

};
