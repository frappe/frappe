// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.provide('frappe.dashboards.chart_sources');

frappe.ui.form.on('Dashboard Chart', {
	setup: function(frm) {
		// fetch timeseries from source
		frm.add_fetch('source', 'timeseries', 'timeseries');
	},


	refresh: function(frm) {
		frm.chart_filters = null;
		frm.add_custom_button('Add Chart to Dashboard', () => {
			const d = new frappe.ui.Dialog({
				title: __('Add to Dashboard'),
				fields: [
					{
						label: __('Select Dashboard'),
						fieldtype: 'Link',
						fieldname: 'dashboard',
						options: 'Dashboard',
					}
				],
				primary_action: (values) => {
					values.chart_name = frm.doc.chart_name;
					frappe.xcall(
						'frappe.desk.doctype.dashboard_chart.dashboard_chart.add_chart_to_dashboard',
						{args: values}
					).then(()=> {
						let dashboard_route_html =
							`<a href = "#dashboard/${values.dashboard}">${values.dashboard}</a>`;
						let message =
							__(`Dashboard Chart ${values.chart_name} add to Dashboard ` + dashboard_route_html);

						frappe.msgprint(message);
					});

					d.hide();
				}
			});

			if (!frm.doc.chart_name) {
				frappe.msgprint(__('Please create chart first'));
			} else {
				d.show();
			}
		});

		frm.set_df_property("filters_section", "hidden", 1);
		frm.trigger('set_time_series');
		frm.set_query('document_type', function() {
			return {
				filters: {
					'issingle': false
				}
			}
		});
		frm.trigger('update_options');
		frm.trigger('set_heatmap_year_options');
		if (frm.doc.report_name) {
			frm.trigger('set_chart_report_filters');
		}

		if (!frappe.boot.developer_mode) {
			frm.set_df_property("custom_options", "hidden", 1);
		}
	},

	source: function(frm) {
		frm.trigger("show_filters");
	},

	set_heatmap_year_options: function(frm) {
		if (frm.doc.type == 'Heatmap') {
			frappe.db.get_doc('System Settings').then(doc => {
				const creation_date = doc.creation;
				frm.set_df_property('heatmap_year', 'options', frappe.dashboard_utils.get_years_since_creation(creation_date));
			});
		}
	},

	chart_type: function(frm) {
		frm.trigger('set_time_series');
		if (frm.doc.chart_type == 'Report') {
			frm.set_query('report_name', () => {
				return {
					filters: {
						'report_type': ['!=', 'Report Builder']
					}
				}
			});
		} else {
			frm.set_value('document_type', '');
		}
	},

	set_time_series: function(frm) {
		// set timeseries based on chart type
		if (['Count', 'Average', 'Sum'].includes(frm.doc.chart_type)) {
			frm.set_value('timeseries', 1);
		} else {
			frm.set_value('timeseries', 0);
		}
	},

	document_type: function(frm) {
		// update `based_on` options based on date / datetime fields
		frm.set_value('source', '');
		frm.set_value('based_on', '');
		frm.set_value('value_based_on', '');
		frm.set_value('filters_json', '[]');
		frm.trigger('update_options');
	},

	report_name: function(frm) {
		frm.set_value('x_field', '');
		frm.set_value('y_axis', []);
		frm.set_df_property('x_field', 'options', []);
		frm.set_value('filters_json', '{}');
		frm.trigger('set_chart_report_filters');
	},


	set_chart_report_filters: function(frm) {
		let report_name = frm.doc.report_name;

		if (report_name) {
			if (frm.doc.filters_json.length > 2) {
				frm.trigger('show_filters');
				frm.trigger('set_chart_field_options');
			} else {
				frappe.report_utils.get_report_filters(report_name).then(filters => {
					if (filters) {
						frm.chart_filters = filters;
						let filter_values = frappe.report_utils.get_filter_values(filters);
						frm.set_value('filters_json', JSON.stringify(filter_values));
					}
					frm.trigger('show_filters');
					frm.trigger('set_chart_field_options');
				});
			}

		}
	},

	set_chart_field_options: function(frm) {
		let filters = frm.doc.filters_json.length > 2? JSON.parse(frm.doc.filters_json): null;
		frappe.xcall(
			'frappe.desk.query_report.run',
			{
				report_name: frm.doc.report_name,
				filters: filters,
				ignore_prepared_report: 1
			}
		).then(data => {
			frm.report_data = data;
			if (!data.chart) {
				frm.set_value('is_custom', 0);
				frm.set_df_property('is_custom', 'hidden', 1);
			} else {
				frm.set_df_property('is_custom', 'hidden', 0);
			}

			if (!frm.doc.is_custom) {
				if (data.result.length) {
					frm.field_options = frappe.report_utils.get_possible_chart_options(data.columns, data);
					frm.set_df_property('x_field', 'options', frm.field_options.non_numeric_fields);
					if (!frm.field_options.numeric_fields.length) {
						frappe.msgprint(__(`Report has no numeric fields, please change the Report Name`));
					} else {
						let y_field_df = frappe.meta.get_docfield('Dashboard Chart Field', 'y_field', frm.doc.name);
						y_field_df.options = frm.field_options.numeric_fields;
					}
				} else {
					frappe.msgprint(__('Report has no data, please modify the filters or change the Report Name'));
				}
			}
		});
	},

	timespan: function(frm) {
		const time_interval_options = {
			"Select Date Range": ["Quarterly", "Monthly", "Weekly", "Daily"],
			"All Time": ["Yearly", "Monthly"],
			"Last Year": ["Quarterly", "Monthly", "Weekly", "Daily"],
			"Last Quarter": ["Monthly", "Weekly", "Daily"],
			"Last Month": ["Weekly", "Daily"],
			"Last Week": ["Daily"]
		};
		if (frm.doc.timespan) {
			frm.set_df_property('time_interval', 'options', time_interval_options[frm.doc.timespan]);
		}
	},

	update_options: function(frm) {
		let doctype = frm.doc.document_type;
		let date_fields = [
			{label: __('Created On'), value: 'creation'},
			{label: __('Last Modified On'), value: 'modified'}
		];
		let value_fields = [];
		let group_by_fields = [];
		let aggregate_function_fields = [];
		let update_form = function() {
			// update select options
			frm.set_df_property('based_on', 'options', date_fields);
			frm.set_df_property('value_based_on', 'options', value_fields);
			frm.set_df_property('group_by_based_on', 'options', group_by_fields);
			frm.set_df_property('aggregate_function_based_on', 'options', aggregate_function_fields);
			frm.trigger("show_filters");
		}


		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				// get all date and datetime fields
				frappe.get_meta(doctype).fields.map(df => {
					if (['Date', 'Datetime'].includes(df.fieldtype)) {
						date_fields.push({label: df.label, value: df.fieldname});
					}
					if (['Int', 'Float', 'Currency', 'Percent'].includes(df.fieldtype)) {
						value_fields.push({label: df.label, value: df.fieldname});
						aggregate_function_fields.push({label: df.label, value: df.fieldname});
					}
					if (['Link', 'Select'].includes(df.fieldtype)) {
						group_by_fields.push({label: df.label, value: df.fieldname});
					}
				});
				update_form();
			});
		} else {
			// update select options
			update_form();
		}

	},

	show_filters: function(frm) {
		frm.chart_filters = [];
		frappe.dashboard_utils.get_filters_for_chart_type(frm.doc).then(filters => {
				if (filters) {
					frm.chart_filters = filters;
				}

				frm.trigger('render_filters_table');
		});
	},

	render_filters_table: function(frm) {
		frm.set_df_property("filters_section", "hidden", 0);
		let is_document_type = frm.doc.chart_type!== 'Report' && frm.doc.chart_type!=='Custom';

		let wrapper = $(frm.get_field('filters_json').wrapper).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 33%">${__('Filter')}</th>
					<th style="width: 33%">${__('Condition')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.filters_json || '[]');
		var filters_set = false;

		let fields;
		if (is_document_type) {
			fields = [
				{
					fieldtype: 'HTML',
					fieldname: 'filter_area',
				}
			];

			if (filters.length > 0) {
				filters.forEach( filter => {
					const filter_row =
						$(`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`);

					table.find('tbody').append(filter_row);
					filters_set = true;
				});
			}
		} else if (frm.chart_filters.length) {
			fields = frm.chart_filters.filter(f => f.fieldname);
			fields.map( f => {
				if (filters[f.fieldname]) {
					let condition = '=';
					const filter_row =
						$(`<tr>
							<td>${f.label}</td>
							<td>${condition}</td>
							<td>${filters[f.fieldname] || ""}</td>
						</tr>`);

					table.find('tbody').append(filter_row);
					filters_set = true;
				}
			});
		}

		if (!filters_set) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Filters")}</td></tr>`);
			table.find('tbody').append(filter_row);
		}

		table.on('click', () => {

			let dialog = new frappe.ui.Dialog({
				title: __('Set Filters'),
				fields: fields,
				primary_action: function() {
					let values = this.get_values();
					if (values) {
						this.hide();
						if (is_document_type) {
							let filters = frm.filter_group.get_filters();
							frm.set_value('filters_json', JSON.stringify(filters));
						} else {
							frm.set_value('filters_json', JSON.stringify(values));
						}

						frm.trigger('show_filters');
						if (frm.doc.chart_type == 'Report') {
							frm.trigger('set_chart_report_filters');
						}
					}
				},
				primary_action_label: "Set"
			});
			frappe.dashboards.filters_dialog = dialog;

			if (is_document_type) {
				frm.filter_group = new frappe.ui.FilterGroup({
					parent: dialog.get_field('filter_area').$wrapper,
					doctype: frm.doc.document_type,
					on_change: () => {},
				});

				frm.filter_group.add_filters_to_filter_group(filters);
			}

			dialog.show();
			//Set query report object so that it can be used while fetching filter values in the report
			frappe.query_report = new frappe.views.QueryReport({'filters': dialog.fields_list});
			frappe.query_reports[frm.doc.report_name].onload
				&& frappe.query_reports[frm.doc.report_name].onload(frappe.query_report);
			dialog.set_values(filters);
		});
	},

});
