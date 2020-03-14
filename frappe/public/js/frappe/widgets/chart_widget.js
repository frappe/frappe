import Widget from "./base_widget.js";
frappe.provide('frappe.dashboards');
frappe.provide('frappe.dashboards.chart_sources');

export default class ChartWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	refresh() {
		this.make_chart();
	}

	customize() {
		this.setup_customize_actions();
	}

	set_body() {
		this.widget.addClass('dashboard-widget-box');
		if (this.width == "Full") {
			this.widget.addClass('full-width');
		}
		this.make_chart();
	}

	set_summary() {
		let summary = $(`<span class="dashboard-summary">$ 54,231</span>`);
		this.title_field.addClass('text-muted');
		summary.prependTo(this.body);
	}

	make_chart() {
		this.body.empty();
		this.get_settings().then(() => {
			this.prepare_chart_object();
			// this.prepare_container();

			this.action_area.empty();
			this.prepare_chart_actions();
			// this.setup_refresh_button();
			this.setup_filter_button();
			if (this.chart_doc.timeseries && this.chart_doc.chart_type !== 'Custom') {
				this.render_time_series_filters();
			}

			this.fetch(this.filters).then(data => {
				if (this.chart_doc.chart_type == 'Report') {
					data = this.get_report_chart_data(data);
				}
				this.update_last_synced();
				this.data = data;
				// Delete existing chart when refreshing
				delete this.dashboardchart;
				this.render();
			});
		});
	}

	setup_customize_actions() {
		this.action_area.empty();
		const buttons = $(`<button type="button" class="btn btn-xs btn-secondary btn-default selected">Resize</button>
					<button class="btn btn-secondary btn-light btn-danger btn-xs"><i class="fa fa-trash" aria-hidden="true"></i></button>`);
		buttons.appendTo(this.action_area);
	}

	setup_refresh_button() {
		const refresh_button = $(`<button class="btn btn-secondary btn-light btn-default btn-xs"><i class="fa fa-refresh" aria-hidden="true"></i></button>`);
		refresh_button.appendTo(this.action_area);
		refresh_button.on('click', () => this.refresh());
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

		frappe.dashboard_utils.render_chart_filters(filters, 'chart-actions', this.action_area, 0);
	}

	fetch_and_update_chart() {
		this.args = {
			timespan: this.selected_timespan,
			time_interval: this.selected_time_interval,
			from_date: this.selected_from_date,
			to_date: this.selected_to_date
		};

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
					.appendTo(this.action_area);

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
		if (result.chart && this.chart_doc.is_custom) {
			return result.chart.data;
		} else {
			let y_fields = [];
			this.chart_doc.y_axis.map( field => {
				y_fields.push(field.y_field);
			});

			let chart_fields = {
				y_fields: y_fields,
				x_field: this.chart_doc.x_field,
				chart_type: this.chart_doc.type,
				color: this.chart_doc.color
			};
			let columns = result.columns.map((col)=> {
				return frappe.report_utils.prepare_field_from_column(col);
			});

			let data = frappe.report_utils.make_chart_options(columns, result, chart_fields).data;
			return data;
		}
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
			});
		} else if (this.chart_doc.chart_type === 'Report') {
			actions.push({
				label: __("{0} Report", [this.chart_doc.report_name]),
				action: 'action-list',
				handler: () => {
					frappe.set_route('query-report', this.chart_doc.report_name);
				}
			})
		}
		this.set_chart_actions(actions);
	}

	setup_filter_button() {
		this.is_document_type = this.chart_doc.chart_type!== 'Report' && this.chart_doc.chart_type!=='Custom';
		this.filter_button =
			$(`<div class="filter-chart btn btn-default btn-xs pull-right">${__("Filter")}</div>`);
		this.filter_button.appendTo(this.action_area);

		this.filter_button.on('click', () => {
			let fields;

			frappe.dashboard_utils.get_filters_for_chart_type(this.chart_doc)
				.then(filters => {
					if (!this.is_document_type) {
						if (!filters) {
							fields = [{
								fieldtype: "HTML",
								options: __("No Filters Set")
							}];
						} else {
							fields = filters.filter(f => {
								if (f.on_change && !f.reqd) {
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
//
	set_chart_actions(actions) {
		this.chart_actions = $(`<div class="chart-actions dropdown pull-right">
			<a class="dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
				<button class="btn btn-default btn-xs"><span class="caret"></span></button>
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
		this.chart_actions.appendTo(this.action_area);
	}

	fetch(filters, refresh=false, args) {
		// this.chart_container.find('.chart-loading-state').removeClass('hide');
		let method = this.settings ? this.settings.method
			: 'frappe.desk.doctype.dashboard_chart.dashboard_chart.get';

		if (this.chart_doc.chart_type == 'Report') {
			args = {
				report_name: this.chart_doc.report_name,
				filters: filters,
			};
		} else {
			args = {
				chart_name: this.chart_doc.name,
				filters: filters,
				refresh: refresh ? 1 : 0,
				time_interval: args && args.time_interval? args.time_interval: null,
				timespan: args && args.timespan? args.timespan: null,
				from_date: args && args.from_date? args.from_date: null,
				to_date: args && args.to_date? args.to_date: null,
			};
		}
		return frappe.xcall(
			method,
			args
		);
	}

	render() {
		const chart_type_map = {
			'Line': 'line',
			'Bar': 'bar',
			'Percentage': 'percentage',
			'Pie': 'pie'
		};

		let colors = [];

		if (this.chart_doc.y_axis.length) {
			this.chart_doc.y_axis.map( field => {
				colors.push(field.color);
			});
		} else if (['Line', 'Bar'].includes(this.chart_doc.type)) {
			colors = [this.chart_doc.color || "light-blue"];
		}

		if (this.data) {
			let chart_args = {
				data: this.data,
				type: chart_type_map[this.chart_doc.type],
				colors: colors,
				axisOptions: {
					xIsSeries: this.chart_doc.timeseries,
					shortenYAxisNumbers: 1
				}
			};
			if (!this.dashboardchart) {
				this.dashboardchart = new frappe.Chart(this.body[0], chart_args);
			} else {
				this.dashboardchart.update(this.data);
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
		return frappe.model.with_doc("Dashboard Chart", this.chart_name).then(chart_doc => {
			this.chart_doc = chart_doc;
			if (this.chart_doc.chart_type == 'Custom') {
				// custom source
				if (frappe.dashboards.chart_sources[this.chart_doc.source]) {
					this.settings = frappe.dashboards.chart_sources[this.chart_doc.source];
					return Promise.resolve();
				} else {
					const method = 'frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config';
					return frappe.xcall(method, {name: this.chart_doc.source}).then(config => {
						frappe.dom.eval(config);
						this.settings = frappe.dashboards.chart_sources[this.chart_doc.source];
					});
				}
			} else if (this.chart_doc.chart_type == 'Report') {
				this.settings = {
					'method': 'frappe.desk.query_report.run'
				};
				return Promise.resolve();
			} else {
				return Promise.resolve();
			}
		});
	}
}