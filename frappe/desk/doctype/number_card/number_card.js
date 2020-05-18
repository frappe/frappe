// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Number Card', {
	refresh: function(frm) {
		frm.set_df_property("filters_section", "hidden", 1);
		frm.trigger('set_options');

		if (frm.doc.type == 'Report') {
			frm.trigger('set_report_filters');
		}

		if (frm.doc.type == 'Custom') {
			if (!frappe.boot.developer_mode) {
				frm.disable_form();
			}
			frm.filters = eval(frm.doc.filters_config);
			frm.trigger('set_filters_description');
		}

		frm.trigger('create_add_to_dashboard_button');
	},

	create_add_to_dashboard_button: function(frm) {
		frm.add_custom_button('Add Card to Dashboard', () => {
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
					values.name = frm.doc.name;
					frappe.xcall(
						'frappe.desk.doctype.number_card.number_card.add_card_to_dashboard',
						{
							args: values
						}
					).then(()=> {
						let dashboard_route_html =
							`<a href = "#dashboard/${values.dashboard}">${values.dashboard}</a>`;
						let message =
							__(`Number Card ${values.name} add to Dashboard ` + dashboard_route_html);

						frappe.msgprint(message);
					});

					d.hide();
				}
			});

			if (!frm.doc.name) {
				frappe.msgprint(__('Please create Card first'));
			} else {
				d.show();
			}
		});
	},

	set_filters_description: function(frm) {
		if (frm.doc.type == 'Custom') {
			frm.fields_dict.filters_config.set_description(`
		Set the filters here. For example:
<pre class="small text-muted">
<code>
[{
	fieldname: "company",
	label: __("Company"),
	fieldtype: "Link",
	options: "Company",
	default: frappe.defaults.get_user_default("Company"),
	reqd: 1
},
{
	fieldname: "account",
	label: __("Account"),
	fieldtype: "Link",
	options: "Account",
	reqd: 1
}]
</code></pre>`);
}
	},

	type: function(frm) {
		frm.trigger('set_filters_description');
		if (frm.doc.type == 'Report') {
			frm.set_query('report_name', () => {
				return {
					filters: {
						'report_type': ['!=', 'Report Builder']
					}
				}
			});
			frm.trigger('set_report_filters');
		}
		frm.set_value('filters_json', 'null');
		frm.filters = null;
		frm.trigger('render_filters_table');
	},

	report_name: function(frm) {
		frm.trigger('set_report_filters');
		frm.set_value('filters_json', 'null');
		frm.filters = null;
	},

	filters_config: function(frm) {
		frm.filters = eval(frm.doc.filters_config);
		const filter_values = frappe.report_utils.get_filter_values(frm.filters);
		frm.set_value('filters_json', JSON.stringify(filter_values));
		frm.trigger('render_filters_table');
	},

	document_type: function(frm) {
		frm.set_query('document_type', function() {
			return {
				filters: {
					'issingle': false
				}
			};
		});
		frm.set_value('filters_json', 'null');
		frm.set_value('aggregate_function_based_on', '');
		frm.trigger('set_options');
	},

	set_options: function(frm) {
		if (!frm.doc.type == 'Document Type') {
			return;
		}

		let aggregate_based_on_fields = [];
		const doctype = frm.doc.document_type;

		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				frappe.get_meta(doctype).fields.map(df => {
					if (frappe.model.numeric_fieldtypes.includes(df.fieldtype)) {
						if (df.fieldtype == 'Currency') {
							if (!df.options || df.options !== 'Company:company:default_currency') {
								return;
							}
						}
						aggregate_based_on_fields.push({label: df.label, value: df.fieldname});
					}
				});

				frm.set_df_property('aggregate_function_based_on', 'options', aggregate_based_on_fields);
			});
			frm.trigger('render_filters_table');
		}
	},

	set_report_filters: function(frm) {
		const report_name = frm.doc.report_name;
		if (report_name) {
			frappe.report_utils.get_report_filters(report_name).then(filters => {
				if (filters) {
					frm.filters = filters;
					const filter_values = frappe.report_utils.get_filter_values(filters);
					if (!JSON.parse(frm.doc.filters_json)) {
						frm.set_value('filters_json', JSON.stringify(filter_values));
					}
				}
				frm.trigger('render_filters_table');
				frm.trigger('set_report_field_options');
			});
		}
	},


	set_report_field_options: function(frm) {
		let filters = JSON.parse(frm.doc.filters_json);
		frappe.xcall(
			'frappe.desk.query_report.run',
			{
				report_name: frm.doc.report_name,
				filters: filters,
				ignore_prepared_report: 1
			}
		).then(data => {
			frm.report_data = data;
			if (data.result.length) {
				frm.field_options = frappe.report_utils.get_field_options_from_report(data.columns, data);
				frm.set_df_property('report_field', 'options', frm.field_options.numeric_fields);
				if (!frm.field_options.numeric_fields.length) {
					frappe.msgprint(__(`Report has no numeric fields, please change the Report Name`));
				}
			} else {
				frappe.msgprint(__('Report has no data, please modify the filters or change the Report Name'));
			}
		});
	},

	render_filters_table: function(frm) {
		frm.set_df_property("filters_section", "hidden", 0);
		let is_document_type = frm.doc.type == 'Document Type';

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

		let filters = JSON.parse(frm.doc.filters_json || 'null');
		let filters_set = false;

		let fields;
		if (is_document_type) {
			fields = [
				{
					fieldtype: 'HTML',
					fieldname: 'filter_area',
				}
			];

			if (filters) {
				filters.forEach( filter => {
					const filter_row =
						$(`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`);

					table.find('tbody').append(filter_row);
				});
				filters_set = true;
			}
		} else if (frm.filters) {
			filters_set = true;
			fields = frm.filters.filter(f => f.fieldname);
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

						frm.trigger('render_filters_table');
						// if (frm.doc.type == 'Report') {
						// 	frm.trigger('set_report_filtres');
						// }
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

				filters && frm.filter_group.add_filters_to_filter_group(filters);
			}

			dialog.show();
			//Set query report object so that it can be used while fetching filter values in the report
			frappe.query_report = new frappe.views.QueryReport({'filters': dialog.fields_list});
			dialog.set_values(filters);
		});
	}
});
