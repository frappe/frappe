
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
			let new_item_html = this.get_dropdown_item_html(new_item);
			$(new_item_html).insertAfter(this.$dropdown_list.find('.points-date-range').eq(0));
		});
	}

	check_seen() {
		let unseen_logs = this.dropdown_items.filter(item => item.seen === 0);
		frappe.call('frappe.social.doctype.energy_point_log.energy_point_log.set_notification_as_seen', {point_logs: unseen_logs});
	}

	get_energy_points_date_range(date) {
		let current_date = frappe.datetime.now_date();
		let prev_week = frappe.datetime.add_days(current_date, -7);
		let prev_month = frappe.datetime.add_months(frappe.datetime.now_date(), -1);
		if (date >= current_date) {
			return 'Today';
		} else if (date > prev_week) {
			return 'Last 7 days';
		} else if (date > prev_month) {
			return 'Last 30 days';
		} else  {
			return 'Older';
		}
	}

	get_energy_points_list(limit) {
		return frappe.db.get_list('Energy Point Log', {
			filters: {
				user: frappe.session.user,
				type: ['not in',['Review']]
			},
			fields:
				['name','user', 'points', 'reference_doctype', 'reference_name', 'reason', 'type', 'seen', 'rule', 'owner', 'creation'],
			limit: limit,
			order_by:'creation desc'
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

		if (this.dropdown_items.length) {
			let date_range= this.get_energy_points_date_range(this.dropdown_items[0].creation);
			body_html += `<li class="points-date-range text-muted">${__(date_range)}</li>`;
			this.dropdown_items.forEach(field => {
				let current_field_date_range = this.get_energy_points_date_range(field.creation);
				if (date_range !== current_field_date_range) {
					body_html+=`<li class="points-date-range text-muted">${__(current_field_date_range)}</li>`;
					date_range=current_field_date_range;
				}
				let item_html = this.get_dropdown_item_html(field);
				if (item_html) body_html += item_html;
			});
		} else {
			body_html += `<li><a href="#" onclick = "return false" class="text-muted text-center">${__('No activity')}</a></li>`;
		}

		let dropdown_html = header_html + body_html +
			`<li><a href="#List/Energy%20Point%20Log/List" class="text-muted text-center">${__('See Full Log')}</a></li>`;
		this.$dropdown_list.html(dropdown_html);
	}

	get_dropdown_item_html(field) {
		let doc_link = frappe.utils.get_form_link(field.reference_doctype,field.reference_name);
		let link_html_string = field.seen? `<a href=${doc_link}>`: `<a href=${doc_link} class="unseen">`;
		let points_html= field.type === 'Auto' || field.type === 'Appreciation'
			? `<div class="points-update positive-points">+${__(field.points)}</div>`
			: `<div class="points-update negative-points">${__(field.points)}</div>`;
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
		owner_name = this.truncate_value(owner_name);
		let message_html = '';
		if (field.type === 'Auto' ) {
			message_html = `For ${__(field.rule)} <span class="points-reason-name text-muted">${__(field.reference_name)}</span>`;
		} else {
			let message;
			if (field.type === 'Appreciation') {
				message = `${__(owner_name)} appreciated your work on `;
			} else if (field.type === 'Criticism') {
				message =  `${__(owner_name)} criticized your work on `;
			} else if (field.type === 'Revert') {
				message =  `${__(owner_name)} reverted your points on `;
			}
			let reason_string = '- "' + this.truncate_value(field.reason) + '"';
			message_html = `${message}<span class="points-reason-name text-muted">${__(field.reference_name)}</span>
				<span class="hidden-xs">${__(reason_string)} </span>`;
		}
		return message_html;
	}

	truncate_value(str) {
		if(str.length > 50) str = str.slice(0,50) + '...';
		return str;
	}
};