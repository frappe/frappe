import Widget from "./base_widget.js";
import { build_summary_item } from "./utils";
frappe.provide("frappe.dashboards");
frappe.provide("frappe.dashboards.chart_sources");

export default class ChartWidget extends Widget {
	constructor(opts) {
		super(opts);
		this.height = this.height || 240;
	}

	get_config() {
		return {
			name: this.name,
			chart_name: this.chart_name,
			label: this.label,
			hidden: this.hidden,
			width: this.width,
		};
	}

	refresh() {
		delete this.dashboard_chart;
		this.set_body();
		this.make_chart();
	}

	set_chart_title() {
		const max_chars = this.widget.width() < 500 ? 20 : 60;
		this.set_title(max_chars);
	}

	set_body() {
		this.widget.addClass("dashboard-widget-box");
		if (this.width == "Full") {
			this.widget.addClass("full-width");
		}
	}

	setup_container() {
		this.body.empty();

		this.loading = $(
			`<div class="chart-loading-state text-muted" style="height: ${this.height}px;">${__(
				"Loading..."
			)}</div>`
		);
		this.loading.appendTo(this.body);

		this.empty = $(
			`<div class="chart-loading-state text-muted" style="height: ${this.height}px;">${__(
				"No Data..."
			)}</div>`
		);
		this.empty.hide().appendTo(this.body);

		this.chart_wrapper = $(`<div></div>`);
		this.chart_wrapper.appendTo(this.body);

		this.set_chart_title();
	}

	set_summary() {
		if (!this.$summary) {
			this.$summary = $(`<div class="report-summary"></div>`).hide();
			this.head.after(this.$summary);
		} else {
			this.$summary.empty();
		}

		this.summary.forEach(summary => {
			build_summary_item(summary).appendTo(this.$summary);
		});
		this.summary.length && this.$summary.show();
	}

	make_chart() {
		this.get_settings().then(() => {
			if (!this.settings) {
				this.deleted = true;
				this.widget.remove();
				return;
			}

			if (!this.chart_settings) {
				this.chart_settings = {};
			}
			this.setup_container();
			this.prepare_chart_object();
			if (!this.in_customize_mode) {
				this.action_area.empty();
				this.prepare_chart_actions();
				this.setup_filter_button();

				if (
					this.chart_doc.timeseries &&
					this.chart_doc.chart_type !== "Custom"
				) {
					this.render_time_series_filters();
				}
			}
			this.fetch_and_update_chart();
		});
	}

	render_time_series_filters() {
		let filters = [
			{
				label: this.chart_settings.timespan || this.chart_doc.timespan,
				options: [
					"Select Date Range",
					"Last Year",
					"Last Quarter",
					"Last Month",
					"Last Week"
				],
				action: selected_item => {
					this.selected_timespan = selected_item;

					if (this.selected_timespan === "Select Date Range") {
						this.render_date_range_fields();
					} else {
						this.selected_from_date = null;
						this.selected_to_date = null;
						if (this.date_field_wrapper) {
							this.date_field_wrapper.hide();

							// Title maybe hidden becuase of date range fields
							// in half width chart
							this.title_field.show();
							this.head.css('flex-direction', "row");
						}

						this.save_chart_config_for_user({
							'timespan': this.selected_timespan,
							'from_date': null,
							'to_date': null

						});
						this.fetch_and_update_chart();
					}
				}
			},
			{
				label: this.chart_settings.time_interval || this.chart_doc.time_interval,
				options: ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"],
				action: selected_item => {
					this.selected_time_interval = selected_item;
					this.save_chart_config_for_user({'time_interval': this.selected_time_interval});
					this.fetch_and_update_chart();
				}
			}
		];

		frappe.dashboard_utils.render_chart_filters(
			filters,
			"chart-actions",
			this.action_area,
			0
		);
	}

	fetch_and_update_chart() {
		this.args = {
			timespan: this.selected_timespan || this.chart_settings.timespan,
			time_interval: this.selected_time_interval || this.chart_settings.time_interval,
			from_date: this.selected_from_date || this.chart_settings.from_date,
			to_date: this.selected_to_date || this.chart_settings.to_date
		};

		this.fetch(this.filters, true, this.args).then(data => {
			if (this.chart_doc.chart_type == "Report") {
				this.summary = data.report_summary;
				data = this.get_report_chart_data(data);
			}

			this.update_chart_object();
			this.data = data;
			this.render();
		});
	}

	render_date_range_fields() {
		if (
			!this.date_field_wrapper ||
			!this.date_field_wrapper.is(":visible")
		) {
			this.date_field_wrapper = $(
				`<div class="dashboard-date-field pull-right"></div>`
			).appendTo(this.action_area);

			if (this.width != "Full" && this.widget.width() < 700) {
				this.title_field.hide();
				this.head.css('flex-direction', "row-reverse");
			}

			this.date_range_field = frappe.ui.form.make_control({
				df: {
					fieldtype: "DateRange",
					fieldname: "from_date",
					placeholder: "Date Range",
					input_class: "input-xs",
					default: [this.chart_settings.from_date, this.chart_settings.to_date],
					reqd: 1,
					change: () => {
						let selected_date_range = this.date_range_field.get_value();
						this.selected_from_date = selected_date_range[0];
						this.selected_to_date = selected_date_range[1];

						if (selected_date_range && selected_date_range.length == 2) {
							this.save_chart_config_for_user({
								'timespan': this.selected_timespan,
								'from_date': this.selected_from_date,
								'to_date': this.selected_to_date,
							});
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
			this.chart_doc.y_axis.map(field => {
				y_fields.push(field.y_field);
			});

			let chart_fields = {
				y_fields: y_fields,
				x_field: this.chart_doc.x_field,
				chart_type: this.chart_doc.type,
				color: this.chart_doc.color
			};
			let columns = result.columns.map(col => {
				return frappe.report_utils.prepare_field_from_column(col);
			});

			let data = frappe.report_utils.make_chart_options(
				columns,
				result,
				chart_fields
			).data;
			return data;
		}
	}

	prepare_chart_actions() {
		let actions = [
			{
				label: __("Refresh"),
				action: "action-refresh",
				handler: () => {
					delete this.dashboard_chart;
					this.make_chart();
				}
			},
			{
				label: __("Edit"),
				action: "action-edit",
				handler: () => {
					frappe.set_route(
						"Form",
						"Dashboard Chart",
						this.chart_doc.name
					);
				}
			},
			{
				label: __("Reset Chart"),
				action: "action-list",
				handler: () => {
					this.reset_chart();
					delete this.dashboard_chart;
					this.make_chart();
				}
			}
		];

		if (this.chart_doc.document_type) {
			actions.push({
				label: __("{0} List", [this.chart_doc.document_type]),
				action: "action-list",
				handler: () => {
					frappe.set_route("List", this.chart_doc.document_type);
				}
			});
		} else if (this.chart_doc.chart_type === "Report") {
			actions.push({
				label: __("{0} Report", [this.chart_doc.report_name]),
				action: "action-list",
				handler: () => {
					frappe.set_route(
						"query-report",
						this.chart_doc.report_name
					);
				}
			});
		}
		this.set_chart_actions(actions);
	}

	setup_filter_button() {
		this.is_document_type =
			this.chart_doc.chart_type !== "Report" &&
			this.chart_doc.chart_type !== "Custom";
		this.filter_button = $(
			`<div class="filter-chart btn btn-default btn-xs pull-right">${__(
				"Filter"
			)}</div>`
		);
		this.filter_button.appendTo(this.action_area);

		this.filter_button.on("click", () => {
			let fields;

			frappe.dashboard_utils
				.get_filters_for_chart_type(this.chart_doc)
				.then(filters => {
					if (!this.is_document_type) {
						if (!filters) {
							fields = [
								{
									fieldtype: "HTML",
									options: __("No Filters Set")
								}
							];
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
						fields = [
							{
								fieldtype: "HTML",
								fieldname: "filter_area"
							}
						];
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
					me.save_chart_config_for_user({'filters': me.filters});
					me.fetch_and_update_chart();
				}
			},
			primary_action_label: "Set"
		});

		if (this.is_document_type) {
			this.create_filter_group_and_add_filters(
				dialog.get_field("filter_area").$wrapper
			);
		}

		dialog.show();
		dialog.set_values(this.filters);
	}

	reset_chart() {
		this.save_chart_config_for_user(null, 1);
		this.chart_settings = {};
		this.filters = null;
	}

	save_chart_config_for_user(config, reset=0) {
		Object.assign(this.chart_settings, config);
		frappe.xcall('frappe.desk.doctype.dashboard_settings.dashboard_settings.save_chart_config', {
			'reset': reset,
			'config': this.chart_settings,
			'chart_name': this.chart_doc.chart_name
		});
	}

	create_filter_group_and_add_filters(parent) {
		this.filter_group = new frappe.ui.FilterGroup({
			parent: parent,
			doctype: this.chart_doc.document_type,
			on_change: () => {}
		});

		frappe.model.with_doctype(this.chart_doc.document_type, () => {
			this.filter_group.add_filters_to_filter_group(this.filters);
		});
	}

	set_chart_actions(actions) {
		/* eslint-disable indent */
		this.chart_actions = $(`<div class="chart-actions dropdown pull-right">
			<a class="dropdown-toggle" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
				<button class="btn btn-default btn-xs"><span class="caret"></span></button>
			</a>
			<ul class="dropdown-menu" style="max-height: 300px; overflow-y: auto;">
				${actions
					.map(
						action =>
							`<li><a data-action="${action.action}">${
								action.label
							}</a></li>`
					)
					.join("")}
			</ul>
		</div>
		`);
		/* eslint-enable indent */

		this.chart_actions.find("a[data-action]").each((i, o) => {
			const action = o.dataset.action;
			$(o).click(actions.find(a => a.action === action));
		});
		this.chart_actions.appendTo(this.action_area);
	}

	fetch(filters, refresh = false, args) {
		let method = this.settings.method;

		if (this.chart_doc.chart_type == "Report") {
			args = {
				report_name: this.chart_doc.report_name,
				filters: filters,
				ignore_prepared_report: 1
			};
		} else {
			args = {
				chart_name: this.chart_doc.name,
				filters: filters,
				refresh: refresh ? 1 : 0,
				time_interval: args && args.time_interval ? args.time_interval : null,
				timespan: args && args.timespan ? args.timespan : null,
				from_date: args && args.from_date ? args.from_date : null,
				to_date: args && args.to_date ? args.to_date : null
			};
		}
		return frappe.xcall(method, args);
	}

	render() {
		const chart_type_map = {
			Line: "line",
			Bar: "bar",
			Percentage: "percentage",
			Pie: "pie",
			Donut: "donut"
		};

		let colors = [];

		if (this.chart_doc.y_axis.length) {
			this.chart_doc.y_axis.map(field => {
				colors.push(field.color);
			});
		} else if (["Line", "Bar"].includes(this.chart_doc.type)) {
			colors = [this.chart_doc.color || "light-blue"];
		}

		if (!this.data || !this.data.labels.length || !Object.keys(this.data).length) {
			this.chart_wrapper.hide();
			this.loading.hide();
			this.$summary.hide();
			this.empty.show();
		} else {
			this.loading.hide();
			this.empty.hide();
			this.chart_wrapper.show();

			let chart_args = {
				data: this.data,
				type: chart_type_map[this.chart_doc.type],
				colors: colors,
				height: this.height,
				axisOptions: {
					xIsSeries: this.chart_doc.timeseries,
					shortenYAxisNumbers: 1
				}
			};

			if (this.chart_doc.custom_options) {
				let custom_options = JSON.parse(this.chart_doc.custom_options);
				for (let key in custom_options) {
					chart_args[key] = custom_options[key];
				}
			}

			if (!this.dashboard_chart) {
				this.dashboard_chart = new frappe.Chart(
					this.chart_wrapper[0],
					chart_args
				);
			} else {
				this.dashboard_chart.update(this.data);
			}
			this.width == "Full" && this.summary && this.set_summary();
		}
	}

	update_last_synced() {
		let last_synced_text = __("Last synced {0}", [
			comment_when(this.chart_doc.last_synced_on)
		]);
		this.footer.html(last_synced_text);
	}

	update_chart_object() {
		frappe.db.get_doc("Dashboard Chart", this.chart_doc.name).then(doc => {
			this.chart_doc = doc;
			this.prepare_chart_object();
			this.update_last_synced();
		});
	}

	prepare_chart_object() {
		let saved_filters = this.chart_settings.filters || null;
		this.filters =
			saved_filters || this.filters || JSON.parse(this.chart_doc.filters_json || "[]");
	}

	get_settings() {
		return frappe.model
			.with_doc("Dashboard Chart", this.chart_name)
			.then(chart_doc => {
				if (chart_doc) {
					this.chart_doc = chart_doc;
					if (this.chart_doc.chart_type == "Custom") {
						// custom source
						if (
							frappe.dashboards.chart_sources[this.chart_doc.source]
						) {
							this.settings =
								frappe.dashboards.chart_sources[
									this.chart_doc.source
								];
							return Promise.resolve();
						} else {
							const method =
								"frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config";
							return frappe
								.xcall(method, { name: this.chart_doc.source })
								.then(config => {
									frappe.dom.eval(config);
									this.settings =
										frappe.dashboards.chart_sources[
											this.chart_doc.source
										];
								});
						}
					} else if (this.chart_doc.chart_type == "Report") {
						this.settings = {
							method: "frappe.desk.query_report.run"
						};
						return Promise.resolve();
					} else {
						this.settings = {
							method: "frappe.desk.doctype.dashboard_chart.dashboard_chart.get"
						};
						return Promise.resolve();
					}
				}
			});
	}
}