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
		frm.set_df_property("filters_section", "hidden", 1);
		frm.trigger('update_options');
		if (frm.doc.report_name) {
			frm.trigger('set_chart_report_filters');
		}
	},

	source: function(frm) {
		frm.trigger("show_filters");
	},

	chart_type: function(frm) {
		if (frm.doc.chart_type == 'Report') {
			frm.set_query('report_name', () => {
				return {
					filters: {
						'report_type': ['!=', 'Report Builder']
					}
				}
			});
		} else {
			// set timeseries based on chart type
			if (['Count', 'Average', 'Sum'].includes(frm.doc.chart_type)) {
				frm.set_value('timeseries', 1);
			} else {
				frm.set_value('timeseries', 0);
			}
			frm.set_value('document_type', '');
		}
	},

	document_type: function(frm) {
		// update `based_on` options based on date / datetime fields
		frm.set_value('source', '');
		frm.set_value('based_on', '');
		frm.set_value('value_based_on', '');
		frm.set_value('filters_json', '{}');
		frm.trigger('update_options');
	},

	report_name: function(frm) {
		frm.set_value('x_field', '');
		frm.set_value('y_field', '');
		frm.set_df_property('x_field', 'options', []);
		frm.set_df_property('y_field', 'options', []);
		frm.set_value('filters_json', '{}');
		frm.trigger('set_chart_report_filters');
	},


	set_chart_report_filters: function(frm) {
		let report_name = frm.doc.report_name;

		if (report_name) {
			if (frm.doc.filters_json.length > 2) {
				frm.trigger("show_filters");
				frm.trigger("set_chart_field_options");
			} else {
				frappe.report_utils.get_report_filters(report_name).then(filters => {
					if (filters) {
						frm.chart_filters = filters;
						let filter_values = frappe.report_utils.get_filter_values(filters);
						frm.set_value('filters_json', JSON.stringify(filter_values));
						frm.trigger("show_filters");
						frm.trigger("set_chart_field_options");
					}

				});
			}

		}
	},

	set_chart_field_options: function(frm) {
		let filters = JSON.parse(frm.doc.filters_json);
		frappe.xcall(
			'frappe.desk.query_report.run',
			{
				report_name: frm.doc.report_name,
				filters: filters
			}
		).then(data => {
			if (data.result.length) {
				let field_options = frappe.report_utils.get_possible_chart_options(data.columns, data);
				frm.set_df_property('x_field', 'options', field_options.non_numeric_fields);
				frm.set_df_property('y_field', 'options', field_options.numeric_fields);
			} else {
				frappe.msgprint(__('Report has no data, please modify the filters or change the Report Name'));
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
		if (frm.chart_filters && frm.chart_filters.length) {
			frm.trigger('render_filters_table');
		} else {
			if (frm.doc.chart_type==='Custom') {
				if (frm.doc.source) {
					frappe.xcall('frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config', {name: frm.doc.source})
						.then(config => {
							frappe.dom.eval(config);
							frm.chart_filters = frappe.dashboards.chart_sources[frm.doc.source].filters;
							frm.trigger('render_filters_table');
						});
				} else {
					frm.chart_filters = [];
					frm.trigger('render_filters_table');
				}
			} else if (frm.doc.chart_type === 'Report') {
				frappe.report_utils.get_report_filters(frm.doc.report_name).then(filters => {
					if (filters) {
						frm.chart_filters = filters;
						frm.trigger('render_filters_table');
					}
				});
			} else {
				// standard filters
				if (frm.doc.document_type) {
					// allow all link and select fields as filters
					frm.chart_filters = [];
					frappe.model.with_doctype(frm.doc.document_type, () => {
						frappe.get_meta(frm.doc.document_type).fields.map(df => {
							if (['Link', 'Select'].includes(df.fieldtype)) {
								let _df = copy_dict(df);

								// nothing is mandatory
								_df.reqd = 0;
								_df.default = null;
								_df.depends_on = null;
								_df.read_only = 0;
								_df.permlevel = 1;
								_df.hidden = 0;

								frm.chart_filters.push(_df);
							}
							frm.trigger('render_filters_table');
						});
					});
				} 
			}

		}
	},

	render_filters_table: function(frm) {
		frm.set_df_property("filters_section", "hidden", 0);
		let fields = frm.chart_filters;

		let wrapper = $(frm.get_field('filters_json').wrapper).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 50%">${__('Filter')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.filters_json || '{}');
		var filters_set = false;

		fields = fields.filter(f => {
			// Ask about MultiSelectList
			// if (f.fieldtype == 'MultiSelectList') {
			// 	if (f.fi)
			// }
			return f.fieldname;
		});
		fields.map( f => {
			if (filters[f.fieldname]) {
				const filter_row = $(`<tr><td>${f.label}</td><td>${filters[f.fieldname] || ""}</td></tr>`);
				table.find('tbody').append(filter_row);
				filters_set = true;
			}
		});

		if (!filters_set) {
			const filter_row = $(`<tr><td colspan="2" class="text-muted text-center">
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
						frm.set_value('filters_json', JSON.stringify(values));
						frm.trigger('show_filters');

						if (frm.doc.chart_type == 'Report') {
							frm.trigger('set_chart_report_filters');
						}
					}
				},
				primary_action_label: "Set"
			});
			dialog.show();
			dialog.set_values(filters);
			frappe.dashboards.filters_dialog = dialog;
		});
	}
});


