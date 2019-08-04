frappe.pages['user-profile'].on_page_load = function(wrapper) {

	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("User Profile"),
	});

	let user_profile = new UserProfile(wrapper)
	$(wrapper).bind('show',()=> {
		user_profile.show();
	});
}

class UserProfile {

	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.sidebar = this.wrapper.find(".layout-side-section");
		this.main_section = this.wrapper.find(".layout-main-section");
	}

	show() {
		this.route = frappe.get_route();
		//validate if user
		if (this.route.length > 1) {
			let user_id = this.route.slice(-1)[0];
			this.check_user_exists(user_id);
		} else {
			this.user_id = frappe.session.user;
			this.make_user_profile();
		}
	}

	check_user_exists(user) {
		frappe.db.exists('User', user).then( exists => {
			if(!exists) {
				frappe.msgprint('User does not exist');
			} else {
				this.user_id = user;
				this.make_user_profile();
			}
		})
	}

	make_user_profile() {
		frappe.set_route('user-profile', this.user_id);
		this.user = frappe.user_info(this.user_id);
		this.page.set_title(this.user.fullname);
		this.setup_user_search();
		this.main_section.empty().append(frappe.render_template('user_profile'));
		this.energy_points = 0;
		this.rank = 0;
		this.month_rank = 0;
		this.render_user_details();
		this.render_points_and_rank();
		this.render_heatmap();
		this.render_years_filter_dropdown();
		this.render_line_chart();
		this.render_percentage_chart('type', 'Type Distribution');
		this.filter_charts();
		this.setup_show_more_activity();
		this.render_user_activity();
	}

	setup_user_search() {
		var me = this;
		this.$user_search_button = this.page.set_secondary_action('Change User', function() {
			me.show_user_search_dialog()
		});
	}

	show_user_search_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __('Change User'),
			fields: [
				{
					fieldtype: 'Link',
					fieldname: 'user',
					options: 'User',
					label: __('User'),
				}
			],
			primary_action_label: __('Go'),
			primary_action: ({ user }) => {
				dialog.hide();
				this.check_user_exists(user);
			}
		});
		dialog.show();
	}

	render_heatmap() {
		this.heatmap = new frappe.Chart('.performance-heatmap', {
			type: 'heatmap',
			countLabel: 'Energy Points',
			data:{},
			discreteDomains: 0,
		});
		this.update_heatmap_data();
	}

	update_heatmap_data(date_from) {
		frappe.xcall('frappe.desk.page.user_profile.user_profile.get_energy_points_heatmap_data', {
			user: this.user_id,
			date: date_from || frappe.datetime.year_start()
		}).then((r)=> {
			this.heatmap.update({dataPoints:r});
		});
	}

	render_years_filter_dropdown() {
		this.user_creation = frappe.boot.user.creation;
		let creation_year = this.get_year(this.user_creation);
		this.year_dropdown = this.wrapper.find('.year-dropdown');
		let dropdown_html = '';
		let current_year = this.get_year(frappe.datetime.now_date());
		for(var year = current_year; year >= creation_year; year--) {
			dropdown_html+=__(`<li><a href="#" onclick="return false">{0}</a></li>`,[year]);
		}
		this.year_dropdown.html(dropdown_html);
	}

	get_year(date_str) {
		return date_str.substring(0,date_str.indexOf('-'));
	}

	render_line_chart() {
		this.line_chart_filters = {'user': this.user_id};
		this.line_chart_data = {
			timespan: 'Last Month',
			time_interval: 'Daily',
			type:'Line',
			value_based_on: "points",
			chart_type: "Sum",
			document_type: "Energy Point Log",
			name: 'Energy Points',
			width: 'half',
			based_on: 'creation'
		}
		this.line_chart = new frappe.Chart( ".performance-line-chart", { // or DOM element
			title: 'Energy Points',
			type: 'line',
			height: 200,
			data: {
				labels: [],
				datasets: [{}]
			},
			colors: ['purple'],
			axisOptions: {
				xIsSeries: 1
			}
		});
		this.update_line_chart_data();
	}

	update_line_chart_data() {
		this.line_chart_data.filters_json = JSON.stringify(this.line_chart_filters);
		frappe.xcall('frappe.desk.doctype.dashboard_chart.dashboard_chart.get', {
			chart: this.line_chart_data,
			no_cache: 1,
		}).then(chart=> {
			this.line_chart.update(chart);
		});
	}

	render_percentage_chart(field, title) {
		frappe.xcall('frappe.desk.page.user_profile.user_profile.get_energy_points_pie_chart_data', {
			user: this.user_id,
			field: field
		}).then(chart=> {
			if(chart.labels.length) {
				this.percentage_chart = new frappe.Chart( '.performance-percentage-chart', { // or DOM element
					title: title,
					type: 'percentage',
					data: {
						labels: chart.labels,
						datasets: chart.datasets
					},
					barOptions: {
						height: 11,
						depth: 1
					},
					height: 160,
					maxSlices: 8,
					colors: ['#5e64ff', '#743ee2', '#ff5858', '#ffa00a', '#feef72', '#28a745', '#98d85b', '#a9a7ac'],
				});
			} else {
				$('.percentage-chart-container').hide();
			}
		});
	}

	//Work on this - look at dashboard.js
	filter_charts() {
		this.year_dropdown.on('click','li a',(e)=> {
			let selected_year = e.currentTarget.textContent;
			this.wrapper.find('.year-filter .filter-label').text(selected_year);
			this.update_heatmap_data(frappe.datetime.obj_to_str(selected_year));
		});

		this.period_dropdown = this.wrapper.find('.period-dropdown').on('click','li a',(e)=> {
			let selected_period = e.currentTarget.textContent;
			this.line_chart_data.timespan = selected_period;
			this.wrapper.find('.period-filter .filter-label').text(selected_period);
			this.update_line_chart_data();
		});

		this.interval_dropdown = this.wrapper.find('.interval-dropdown').on('click','li a',(e)=> {
			let selected_interval = e.currentTarget.textContent;
			this.line_chart_data.time_interval = selected_interval;
			this.wrapper.find('.interval-filter .filter-label').text(selected_interval);
			this.update_line_chart_data();
		});

		this.type_dropdown = this.wrapper.find('.type-dropdown').on('click','li a',(e)=> {
			let selected_type = e.currentTarget.textContent;
			if(selected_type === 'All') delete this.line_chart_filters.type;
			else this.line_chart_filters.type = selected_type;
			this.wrapper.find('.type-filter .filter-label').text(selected_type);
			this.update_line_chart_data();
		});

		this.field_dropdown = this.wrapper.find('.field-dropdown').on('click','li a',(e)=> {
			let selected_field = e.currentTarget.textContent;
			let fieldname = $(e.currentTarget).attr('data-fieldname')
			this.wrapper.find('.field-filter .filter-label').text(selected_field);
			let title = selected_field + ' Distribution';
			this.render_percentage_chart(fieldname, title);
		});
	}

	edit_profile() {
		const edit_profile_dialog = new frappe.ui.Dialog({
			title: __('Edit Profile'),
			fields: [
				{
					fieldtype: 'Attach Image',
					fieldname: 'user_image',
					label: 'Profile Image',
				},
				{
					fieldtype: 'Data',
					fieldname: 'interest',
					label: 'Interests',
				},
				{
					fieldtype: 'Column Break'
				},
				{
					fieldtype: 'Data',
					fieldname: 'location',
					label: 'Location',
				},
				{
					fieldtype: 'Section Break',
					fieldname: 'Interest',
				},
				{
					fieldtype: 'Small Text',
					fieldname: 'bio',
					label: 'Bio',
				}
			],
			primary_action: values => {
				edit_profile_dialog.disable_primary_action();
				frappe.xcall('frappe.desk.page.user_profile.user_profile.update_profile_info', {
						profile_info: values
					})
					.then(user => {
						user.image = user.user_image;
						this.user = Object.assign(values, user);
						edit_profile_dialog.hide();
						this.render_user_details();
					})
					.finally(() => {
						edit_profile_dialog.enable_primary_action();
					});
			},
			primary_action_label: __('Save')
		});
		edit_profile_dialog.set_values({
			user_image: this.user.image,
			location: this.user.location,
			interest: this.user.interest,
			bio: this.user.bio
		});
		edit_profile_dialog.show();
	}

	render_user_details() {
		this.sidebar.empty().append(frappe.render_template('user_profile_sidebar', {
			user_image: frappe.avatar(this.user_id,'avatar-frame', 'user_image', this.user.image),
			user_abbr: this.user.abbr,
			user_location: this.user.location,
			user_interest: this.user.interest,
			user_bio: this.user.bio,
		}));
		if(this.user_id !== frappe.session.user) {
			this.wrapper.find('.profile-links').hide();
		} else {
			this.wrapper.find(".edit-profile-link").on("click", () => {
				this.edit_profile();
			});
			this.wrapper.find(".user-settings-link").on("click", () => {
				this.go_to_user_settings();
			});
		}
	}

	get_user_energy_points_and_rank(date) {
		return frappe.xcall('frappe.desk.page.user_profile.user_profile.get_user_points_and_rank', {
			user: this.user_id,
			date: date || null,
		})
		.then(user => {
			if(user[0]) {
				let user_info = user[0];
				if(!this.energy_points) this.energy_points = user_info[1];
				if(!date) {
					this.rank = user_info[2];
				} else {
					this.month_rank = user_info[2];
				}
			}
		})
	}

	render_points_and_rank() {
		let profile_details_el = this.wrapper.find('.profile-details')
		this.get_user_energy_points_and_rank().then(()=> {
			let html = $(__(`<p class="user-energy-points text-muted">Energy Points: <span class="rank">{0}</span></p>
				<p class="user-energy-points text-muted">Rank: <span class="rank">{1}</span></p>`, [this.energy_points, this.rank]));
				profile_details_el.append(html);
			this.get_user_energy_points_and_rank(frappe.datetime.month_start()).then(()=> {
				let html = $(__(`<p class="user-energy-points text-muted">Monthly Rank: <span class="rank">{0}</span></p>`, [this.month_rank]));
				profile_details_el.append(html);
			})
		})
	}

	go_to_user_settings() {
		frappe.set_route('Form', 'User', this.user_id);
	}

	render_user_activity(append) {
		this.$recent_activity_list = $('.recent-activity-list');
		let get_recent_energy_points_html = (field) => {
			let points_html= field.type === 'Auto' || field.type === 'Appreciation'
			? __(`<div class="points-update positive-points">+{0}</div>`, [field.points])
			: __(`<div class="points-update negative-points">+{0}</div>`, [field.points]);
			let message_html = this.get_message_html(field);

			return `<p class="recent-points-item">
						${points_html}
						<span class="points-reason">
							${message_html}
						</span>
					</p>`;
		}
		frappe.xcall('frappe.desk.page.user_profile.user_profile.get_energy_points_list', {
			start:this.activity_start,
			limit: this.activity_end,
			user: this.user_id
		}).then(list=> {
			if(!list.length) {
				this.wrapper.find('.show-more-activity a').html('No More Activity');
			}
			let html = list.map(get_recent_energy_points_html).join('');
			if(append) this.$recent_activity_list.append(html);
			else this.$recent_activity_list.html(html);
		})
	}

	get_message_html(field) {
		let owner_name = frappe.user.full_name(field.owner).trim();
		let doc_link = frappe.utils.get_form_link(field.reference_doctype, field.reference_name);
		let message_html = '';
		if(field.type === 'Auto' ) {
			message_html = __(`For {0} <a class="points-doc-link text-muted" href=${doc_link}>{1}</a>`,
				[field.rule, field.reference_name, field.reason]);
		} else {
			let user_str = this.user_id === frappe.session.user ? 'your': frappe.user.full_name(field.user) + "'s";
			let message;
			if(field.type === 'Appreciation') {
				message = __('{0} appreciated {1} work on ', [owner_name, user_str]);
			} else if(field.type === 'Criticism') {
				message =  __('{0} criticized {1} work on ', [owner_name, user_str]);
			} else if(field.type === 'Revert') {
				message =  __('{0} reverted {1} points on ', [owner_name, user_str]);
			}
			message_html = __(`{0}<a class="points-doc-link text-muted" href=${doc_link}>{1}</a>
				<span class="hidden-xs"> - {2} </span>`, [message, field.reference_name, field.reason]);
		}
		return message_html;
	}

	setup_show_more_activity() {
		this.activity_start = 0;
		this.activity_end = 10;
		this.wrapper.find('.show-more-activity').on('click', ()=>this.show_more_activity());
	}

	show_more_activity() {
		this.activity_start = this.activity_end;
		this.activity_end+=10;
		this.render_user_activity(true);
	}

}



