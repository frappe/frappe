// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Forecast Template', {
	setup: function(frm) {
		frm.set_query('document_type', () => {
			return {
				query: 'frappe.core.doctype.forecast_template.forecast_template.get_doctypes'
			};
		})
	},

	refresh: function(frm) {
		frm.trigger("setup_forecast_fields");
		frm.trigger("set_description_for_forecasting_method");

		if (!frm.is_new() && in_list(["Open", "Error"], frm.doc.status)) {
			frm.trigger("prepare_forecast_data");
		}

		if (frm.doc.status === 'Completed') {
			let based_on_field = frm.doc.forecast_field.split(',');
			frm.add_custom_button(__("View Report"), () => {
				frappe.route_options = {
					"forecast_template": frm.doc.name,
					"document_type": frm.doc.document_type,
					"based_on": based_on_field[1] + ' (' + based_on_field[0] + ')'
				};
				frappe.set_route("query-report", "Exponential Smoothing Forecast")
			});
		}
	},

	prepare_forecast_data: function(frm) {
		frm.add_custom_button(__("Prepare Forecast Data"), () => {
			frappe.call({
				method: "frappe.core.doctype.forecast_template.forecast_template.prepare_forecast_data",
				freeze: true,
				args: {
					docname: frm.doc.name
				},
				callback: function() {
					frm.reload_doc();
				}
			})
		}).addClass("btn-primary");
	},

	forecasting_method: function(frm) {
		frm.trigger("set_description_for_forecasting_method");
	},

	set_description_for_forecasting_method: function(frm) {
		const forecasting_method_description = [
			"<b>Level</b>: The average value in the series.",
			"<b>Trend</b>: The increasing or decreasing value in the series.",
			"<b>Seasonality</b>: The repeating short-term cycle in the series."
		];

		const forecasting_method_index = {
			"Single Exponential Smoothing": 0,
			"Double Exponential Smoothing": 1,
			"Triple Exponential Smoothing": 2,
		};

		let description = "";
		let index = forecasting_method_index[frm.doc.forecasting_method];

		forecasting_method_description.forEach((data, i) => {
			if (index >= i) {
				description += data;
			}

			if (index > i) {
				description += '<br>';
			}
		});

		frm.set_df_property("forecasting_method", "description", description);
	},

	document_type: function(frm) {
		if (!frappe.boot.developer_mode) {
			frm.set_value("is_custom", 1);
		}

		frm.trigger("setup_forecast_fields");
		frm.set_value('forecast_filters', '[]');
		frm.trigger("render_filters_table");
	},

	onload: function(frm) {
		frm.trigger("setup_filters");
		frm.trigger("render_filters_table");
	},

	from_date: function(frm) {
		if (frm.doc.from_date) {
			frm.set_value("to_date", frappe.datetime.add_months(frm.doc.from_date, 12));
		}
	},

	setup_filters: function(frm) {
		if (frm.doc.document_type) {
			frappe.model.with_doctype(frm.doc.document_type, () => set_field_options(frm));
		}
	},

	setup_forecast_fields: function(frm) {
		if (frm.doc.document_type) {
			frappe.call({
				method: "frappe.core.doctype.forecast_template.forecast_template.get_doctype_fields",
				freeze: true,
				args: {
					doctype: frm.doc.document_type
				},
				callback: function(r) {
					if (r && r.message) {
						let numeric_fields = r.message.map(d => {
							if (in_list(["Int", "Float", "Currency"], d.fieldtype)) {
								return { label: d.label + ' (' + d.parent + ')', value: [d.parent, d.fieldname] };
							}
						});

						frm.set_df_property("forecast_field", "options", numeric_fields.filter(d => d));

						let fields = r.message.map(d => {
							if (frappe.model.no_value_type.indexOf(d.fieldtype) === -1 ||
									(d.fieldtype === 'Table' && !d.read_only)) {
								return { label: d.label + ' (' + d.parent + ')', value: [d.parent, d.fieldname] };
							}
						});

						frappe.meta.get_docfield("Forecast Column",
							"label", frm.doc.name).options = [""].concat(fields.filter(d => d));

						let date_fields = r.message.map(d => {
							if (in_list(["Date"], d.fieldtype) && d.parent == frm.doc.document_type) {
								return { label: d.label + ' (' + d.parent + ')', value: d.fieldname };
							}
						});

						frm.set_df_property("date_field", "options", date_fields.filter(d => d));
					}
				}
			});
		}
	},

	render_filters_table: function(frm) {
		frm.set_df_property("filters_section", "hidden", 0);
		let is_document_type = frm.doc.chart_type!== 'Report' && frm.doc.chart_type!=='Custom';
		let is_dynamic_filter = f => ['Date', 'DateRange'].includes(f.fieldtype) && f.default;

		let wrapper = $(frm.get_field('forecast_filters').wrapper).empty();
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

		let filters = JSON.parse(frm.doc.forecast_filters || '[]');
		var filters_set = false;

		// Set dynamic filters for reports
		if (frm.doc.chart_type == 'Report') {
			let set_filters = false;
			frm.chart_filters.forEach(f => {
				if (is_dynamic_filter(f)) {
					filters[f.fieldname] = f.default;
					set_filters = true;
				}
			});
			set_filters && frm.set_value('forecast_filters', JSON.stringify(filters));
		}

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
				fields: fields.filter(f => !is_dynamic_filter(f)),
				primary_action: function() {
					this.hide();

					if (is_document_type) {
						let filters = frm.filter_group.get_filters() || [];
						frm.set_value('forecast_filters', JSON.stringify(filters));
						frm.trigger("render_filters_table");
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

			if (frm.doc.chart_type == 'Report') {
				//Set query report object so that it can be used while fetching filter values in the report
				frappe.query_report = new frappe.views.QueryReport({'filters': dialog.fields_list});
				frappe.query_reports[frm.doc.report_name]
					&& frappe.query_reports[frm.doc.report_name].onload
						&& frappe.query_reports[frm.doc.report_name].onload(frappe.query_report);
			}

			dialog.set_values(filters);
		});
	},
});

frappe.ui.form.on("Forecast Column", {
	label: function(frm, doctype, name) {
		let row = locals[doctype][name]
		if (frm.doc.doctype) {
			frappe.call({
				method: "frappe.core.doctype.forecast_template.forecast_template.get_field_details",
				freeze: true,
				args: {
					doctype: frm.doc.document_type,
					label: row.label
				},
				callback: function(r) {
					if (r && r.message) {
						frappe.model.set_value(doctype, name, {
							"fieldname": r.message.fieldname,
							"document_type": r.message.parent,
							"field_type": r.message.fieldtype,
							"field_options": r.message.options,
							"field_label": r.message.label
						});
					}
				}
			});
		}
	}
});
