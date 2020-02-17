// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.dashboards');
frappe.provide('frappe.dashboards.chart_sources');


frappe.pages['dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard"),
		single_column: true
	});

	frappe.dashboard = new Dashboard(wrapper);
	$(wrapper).bind('show', function() {
		frappe.dashboard.show();
	});
};

class Dashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		$(`<div class="dashboard">
			<div class="dashboard-graph row"></div>
		</div>`).appendTo(this.wrapper.find(".page-content").empty());
		this.container = this.wrapper.find(".dashboard-graph");
		this.page = wrapper.page;
	}

	show() {
		this.route = frappe.get_route();
		if (this.route.length > 1) {
			// from route
			this.show_dashboard(this.route.slice(-1)[0]);
		} else {
			// last opened
			if (frappe.last_dashboard) {
				frappe.set_route('dashboard', frappe.last_dashboard);
			} else {
				// default dashboard
				frappe.db.get_list('Dashboard', {filters: {is_default: 1}}).then(data => {
					if (data && data.length) {
						frappe.set_route('dashboard', data[0].name);
					} else {
						// no default, get the latest one
						frappe.db.get_list('Dashboard', {limit: 1}).then(data => {
							if (data && data.length) {
								frappe.set_route('dashboard', data[0].name);
							} else {
								// create a new dashboard!
								frappe.new_doc('Dashboard');
							}
						});
					}
				});
			}
		}
	}

	show_dashboard(current_dashboard_name) {
		if(this.dashboard_name !== current_dashboard_name) {
			this.dashboard_name = current_dashboard_name;
			let title = this.dashboard_name;
			if (!this.dashboard_name.toLowerCase().includes(__('dashboard'))) {
				// ensure dashboard title has "dashboard"
				title = __('{0} Dashboard', [title]);
			}
			this.page.set_title(title);
			this.set_dropdown();
			this.container.empty();
			this.refresh();
		}
		this.charts = {};
		frappe.last_dashboard = current_dashboard_name;
	}

	refresh() {
		this.get_dashboard_doc().then((doc) => {
			this.dashboard_doc = doc;
			this.charts = this.dashboard_doc.charts;

			this.charts.map((chart) => {
				let chart_container = $("<div></div>");
				chart_container.appendTo(this.container);

				frappe.model.with_doc("Dashboard Chart", chart.chart).then( chart_doc => {
					let dashboard_chart = new DashboardChart(chart_doc, chart_container);
					dashboard_chart.show();
				});
			});
		});
	}

	get_dashboard_doc() {
		return frappe.model.with_doc('Dashboard', this.dashboard_name);
	}

	set_dropdown() {
		this.page.clear_menu();

		this.page.add_menu_item('Edit...', () => {
			frappe.set_route('Form', 'Dashboard', frappe.dashboard.dashboard_name);
		}, 1);

		this.page.add_menu_item('New...', () => {
			frappe.new_doc('Dashboard');
		}, 1);

		frappe.db.get_list("Dashboard").then(dashboards => {
			dashboards.map(dashboard => {
				let name = dashboard.name;
				if(name != this.dashboard_name){
					this.page.add_menu_item(name, () => frappe.set_route("dashboard", name));
				}
			});
		});
	}
}

class DashboardChart {
	constructor(chart_doc, chart_container) {
		this.chart_doc = chart_doc;
		this.container = chart_container;
	}

	show() {
		this.get_settings().then(() => {
			this.prepare_chart_object();
			this.prepare_container();
			this.setup_filter_button();

			if (this.chart_doc.timeseries && this.chart_doc.chart_type !== 'Custom') {
				this.render_time_series_filters();
			}
			this.prepare_chart_actions();
			this.fetch(this.filters).then( data => {
				if (this.chart_doc.chart_type == 'Report') {
					data = this.get_report_chart_data(data);
				}
				this.update_last_synced();
				this.data = data;
				this.render();
			});
		});
	}

	prepare_container() {
		const column_width_map = {
			"Half": "6",
			"Full": "12",
		};
		let columns = column_width_map[this.chart_doc.width];
		this.chart_container = $(`<div class="col-sm-${columns} chart-column-container">
			<div class="chart-wrapper">
				<div class="chart-loading-state text-muted">${__("Loading...")}</div>
				<div class="chart-empty-state hide text-muted">${__("No Data")}</div>
			</div>
		</div>`);
		this.chart_container.appendTo(this.container);

		let last_synced_text = $(`<span class="text-muted last-synced-text"></span>`);
		last_synced_text.prependTo(this.chart_container);
	}

	render_time_series_filters() {
		let filters = [
			{
				label: this.chart_doc.timespan,
				options: ['Select Date Range', 'Last Year', 'Last Quarter', 'Last Month', 'Last Week'],
				action: (selected_item) => {
					this.selected_timespan = selected_item;

					if (this.selected_timespan === 'Select Date Range') {
						this.render_date_range_fields();
					} else {
						this.selected_from_date = null;
						this.selected_to_date = null;
						if (this.date_field_wrapper) this.date_field_wrapper.hide();
						this.fetch_and_update_chart();
					}
				}
			},
			{
				label: this.chart_doc.time_interval,
				options: ['Yearly', 'Quarterly', 'Monthly', 'Weekly', 'Daily'],
				action: (selected_item) => {
					this.selected_time_interval = selected_item;
					this.fetch_and_update_chart();
				}
			},
		];

		frappe.dashboard_utils.render_chart_filters(filters, 'chart-actions', this.chart_container, 1);
	}

	fetch_and_update_chart() {
		this.args = {
			timespan: this.selected_timespan,
			time_interval: this.selected_time_interval,
			from_date: this.selected_from_date,
			to_date: this.selected_to_date
		}

		this.fetch(this.filters, true, this.args).then(data => {
			if (this.chart_doc.chart_type == 'Report') {
				data = this.get_report_chart_data(data);
			}

			this.update_chart_object();
			this.data = data;
			this.render();
		});
	}

	render_date_range_fields() {
		if (!this.date_field_wrapper || !this.date_field_wrapper.is(':visible')) {
			this.date_field_wrapper = 
				$(`<div class="dashboard-date-field pull-right"></div>`)
					.insertBefore(this.chart_container.find('.chart-wrapper'));

			this.date_range_field = frappe.ui.form.make_control({
				df: {
					fieldtype: 'DateRange',
					fieldname: 'from_date',
					placeholder: 'Date Range',
					input_class: 'input-xs',
					reqd: 1,
					change: () => {
						let selected_date_range = this.date_range_field.get_value();
						this.selected_from_date = selected_date_range[0];
						this.selected_to_date = selected_date_range[1];

						if (selected_date_range && selected_date_range.length == 2) {
							this.fetch_and_update_chart();
						}
					}
				},
				parent: this.date_field_wrapper,
				render_input: 1
			});
		}
	}

	get_report_chart_data(result) {
		let chart_fields = {
			y_field: this.chart_doc.y_field,
			x_field: this.chart_doc.x_field,
			chart_type: this.chart_doc.type,
			color: this.chart_doc.color
		}
		let columns = result.columns.map((col)=> {
			return frappe.report_utils.prepare_field_from_column(col);
		});

		let data = frappe.report_utils.make_chart_options(columns, result, chart_fields).data;
		return data;
	}

	prepare_chart_actions() {
		let actions = [
			{
				label: __("Refresh"),
				action: 'action-refresh',
				handler: () => {
					this.fetch_and_update_chart();
				}
			},
			{
				label: __("Edit..."),
				action: 'action-edit',
				handler: () => {
					frappe.set_route('Form', 'Dashboard Chart', this.chart_doc.name);
				}
			}
		];
		if (this.chart_doc.document_type) {
			actions.push({
				label: __("{0} List", [this.chart_doc.document_type]),
				action: 'action-list',
				handler: () => {
					frappe.set_route('List', this.chart_doc.document_type);
				}
			})
		}
		this.set_chart_actions(actions);
	}

	setup_filter_button() {
		
		this.is_document_type = this.chart_doc.chart_type!== 'Report' && this.chart_doc.chart_type!=='Custom';
		this.filter_button = $(`<div class="filter-chart btn btn-default btn-xs pull-right">${__("Set Filters")}</div>`);
		this.filter_button.prependTo(this.chart_container);

		this.filter_button.on('click', () => {
			let fields;
			frappe.dashboard_utils.get_filters_for_chart_type(this.chart_doc)
				.then((filters) => {
					if (!this.is_document_type) {
						if (!filters) {
							fields = [{
								fieldtype:"HTML",
								options:__("No Filters Set")
							}];
						} else {
							fields = filters.filter(f => {
								if (f.on_change) {
									return false;
								}
								if (f.get_query || f.get_data) {
									f.read_only = 1;
								}
								return f.fieldname;
							});
						}
					} else {
						fields = [{
							fieldtype: 'HTML',
							fieldname: 'filter_area',
						}];
					}

					this.setup_filter_dialog(fields);
				});
		});
	}

	setup_filter_dialog(fields) {

		let me = this;
		let dialog = new frappe.ui.Dialog({
			title: __(`Set Filters for ${this.chart_doc.chart_name}`),
			fields: fields,
			primary_action: function() {
				let values = this.get_values();
				if (values) {
					this.hide();
					if (me.is_document_type) {
						me.filters = me.filter_group.get_filters();
					} else {
						me.filters = values;
					}
					me.fetch_and_update_chart();
				}
			},
			primary_action_label: "Set"
		});

		if (this.is_document_type) {
			this.create_filter_group_and_add_filters(dialog.get_field('filter_area').$wrapper);
		}

		dialog.show();
		dialog.set_values(this.filters);	
	
	}

	create_filter_group_and_add_filters(parent) {
		this.filter_group = new frappe.ui.FilterGroup({
			parent: parent,
			doctype: this.chart_doc.document_type,
			on_change: () => {},
		});

		frappe.model.with_doctype(this.chart_doc.document_type, () => {
			this.filter_group.add_filters_to_filter_group(this.filters);
		});
	}

	set_chart_actions(actions) {
		this.chart_actions = $(`<div class="chart-actions btn-group dropdown pull-right">
			<a class="dropdown-toggle" data-toggle="dropdown"
				aria-haspopup="true" aria-expanded="false"> <button class="btn btn-default btn-xs"><span class="caret"></span></button>
			</a>
			<ul class="dropdown-menu" style="max-height: 300px; overflow-y: auto;">
				${actions.map(action => `<li><a data-action="${action.action}">${action.label}</a></li>`).join('')}
			</ul>
		</div>
		`);

		this.chart_actions.find("a[data-action]").each((i, o) => {
			const action = o.dataset.action;
			$(o).click(actions.find(a => a.action === action));
		});
		this.chart_actions.prependTo(this.chart_container);
	}

	fetch(filters, refresh=false, args) {
		this.chart_container.find('.chart-loading-state').removeClass('hide');
		let method = this.settings ? this.settings.method
			: 'frappe.desk.doctype.dashboard_chart.dashboard_chart.get';

		if (this.chart_doc.chart_type == 'Report') {
			args = {
				report_name: this.chart_doc.report_name,
				filters: filters,
			}
		} else {
			args = {
				chart_name: this.chart_doc.name,
				filters: filters,
				refresh: refresh ? 1 : 0,
				time_interval: args && args.time_interval? args.time_interval: null,
				timespan: args && args.timespan? args.timespan: null,
				from_date: args && args.from_date? args.from_date: null,
				to_date: args && args.to_date? args.to_date: null,
			}
		}
		return frappe.xcall(
			method,
			args
		);
	}

	render() {
		const chart_type_map = {
			"Line": "line",
			"Bar": "bar",
		};

		this.chart_container.find('.chart-loading-state').addClass('hide');
		if (!this.data) {
			this.chart_container.find('.chart-empty-state').removeClass('hide');
		} else {
			let chart_args = {
				title: this.chart_doc.chart_name,
				data: this.data,
				type: chart_type_map[this.chart_doc.type],
				colors: [this.chart_doc.color || "light-blue"],
				axisOptions: {
					xIsSeries: this.chart_doc.timeseries,
					shortenYAxisNumbers: 1
				}
			};
			if (!this.chart) {
				this.chart = new frappe.Chart(this.chart_container.find(".chart-wrapper")[0], chart_args);
			} else {
				this.chart.update(this.data);
			}
		}
	}

	update_last_synced() {
		let last_synced_text = __("Last synced {0}", [comment_when(this.chart_doc.last_synced_on)]);
		this.container.find(".last-synced-text").html(last_synced_text);
	}

	update_chart_object() {
		frappe.db.get_doc("Dashboard Chart", this.chart_doc.name).then(doc => {
			this.chart_doc = doc;
			this.prepare_chart_object();
			this.update_last_synced();
		});
	}

	prepare_chart_object() {
		this.filters = this.filters || JSON.parse(this.chart_doc.filters_json || '[]');
	}

	get_settings() {
		if (this.chart_doc.chart_type == 'Custom') {
			// custom source
			if (frappe.dashboards.chart_sources[this.chart_doc.source]) {
				this.settings = frappe.dashboards.chart_sources[this.chart_doc.source];
				return Promise.resolve();
			} else {
				return frappe.xcall('frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config',
					{name: this.chart_doc.source})
					.then(config => {
						frappe.dom.eval(config);
						this.settings = frappe.dashboards.chart_sources[this.chart_doc.source];
					});
			}
		} else if (this.chart_doc.chart_type == 'Report') {
			this.settings = {
				'method': 'frappe.desk.query_report.run',
			}
			return Promise.resolve();
		} else {
			return Promise.resolve();
		}
	}
}