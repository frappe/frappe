frappe.dashboard_utils = {
	render_chart_filters: function(filters, button_class, container, append) {
		filters.forEach(filter => {
			let chart_filter_html =
				`<div class="${button_class} btn-group dropdown pull-right">
					<a class="dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
						<button class="btn btn-default btn-xs">
							<span class="filter-label">${filter.label}</span>
							<span class="caret"></span>
						</button>
				</a>`;
			let options_html;

			if (filter.fieldnames) {
				options_html = filter.options.map((option, i) =>
					`<li><a data-fieldname = "${filter.fieldnames[i]}">${option}</a></li>`).join('');
			} else {
				options_html = filter.options.map( option => `<li><a>${option}</a></li>`).join('');
			}

			let dropdown_html = chart_filter_html + `<ul class="dropdown-menu">${options_html}</ul></div>`;
			let $chart_filter = $(dropdown_html);

			if (append) {
				$chart_filter.prependTo(container);
			} else $chart_filter.appendTo(container);

			$chart_filter.find('.dropdown-menu').on('click', 'li a', (e) => {
				let $el = $(e.currentTarget);
				let fieldname;
				if ($el.attr('data-fieldname')) {
					fieldname = $el.attr('data-fieldname');
				}

				let selected_item = $el.text();
				$el.parents(`.${button_class}`).find('.filter-label').text(selected_item);
				filter.action(selected_item, fieldname);
			});
		});

	},

	get_filters_for_chart_type: function(chart) {
		if (chart.chart_type === 'Custom' && chart.source) {
			const method = 'frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config';
			return frappe.xcall(method, {name: chart.source}).then(config => {
				frappe.dom.eval(config);
				return frappe.dashboards.chart_sources[chart.source].filters;
			});
		} else if (chart.chart_type === 'Report') {
			return frappe.report_utils.get_report_filters(chart.report_name).then(filters => {
				return filters;
			});
		} else {
			return Promise.resolve();
		}
	},

	get_dashboard_settings() {
		return frappe.db.get_list('Dashboard Settings', {
			filters: {
				name: frappe.session.user
			},
			fields: ['*']
		}).then(settings => {
			if (!settings.length) {
				return this.create_dashboard_settings().then(settings => {
					return settings;
				});
			} else {
				return settings[0];
			}
		});
	},

	create_dashboard_settings() {
		return frappe.xcall(
			'frappe.desk.doctype.dashboard_settings.dashboard_settings.create_dashboard_settings',
			{
				user: frappe.session.user
			}
		).then(settings => {
			return settings;
		});
	},

	get_years_since_creation(creation) {
		//Get years since user account created
		let creation_year = this.get_year(creation);
		let current_year = this.get_year(frappe.datetime.now_date());
		let years_list = [];
		for (var year = current_year; year >= creation_year; year--) {
			years_list.push(year);
		}
		return years_list;
	},

	get_year(date_str) {
		return date_str.substring(0, date_str.indexOf('-'));
	}

};