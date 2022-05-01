// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Number Card', {
	refresh: function(frm) {
		if (!frappe.boot.developer_mode && frm.doc.is_standard) {
			frm.disable_form();
		}
		frm.set_df_property("filters_section", "hidden", 1);
		frm.set_df_property("dynamic_filters_section", "hidden", 1);
		frm.trigger('set_options');

		if (!frm.doc.type) {
			frm.set_value('type', 'Document Type');
		}

		if (frm.doc.type == 'Report' && frm.doc.report_name) {
			frm.trigger('set_report_filters');
		}

		if (frm.doc.type == 'Custom') {
			if (!frappe.boot.developer_mode) {
				frm.disable_form();
			}
			frm.filters = eval(frm.doc.filters_config);
			frm.trigger('set_filters_description');
			frm.trigger('set_method_description');
			frm.trigger('render_filters_table');
		}
		frm.trigger('set_parent_document_type');

		if (!frm.is_new()) {
			frm.trigger('create_add_to_dashboard_button');
		}
	},

	create_add_to_dashboard_button: function(frm) {
		frm.add_custom_button('Add Card to Dashboard', () => {
			const dialog = frappe.dashboard_utils.get_add_to_dashboard_dialog(
				frm.doc.name,
				'Number Card',
				'frappe.desk.doctype.number_card.number_card.add_card_to_dashboard'
			);

			if (!frm.doc.name) {
				frappe.msgprint(__('Please create Card first'));
			} else {
				dialog.show();
			}
		});
	},

	before_save: function(frm) {
		let dynamic_filters = JSON.parse(frm.doc.dynamic_filters_json || 'null');
		let static_filters = JSON.parse(frm.doc.filters_json || 'null');
		static_filters =
			frappe.dashboard_utils.remove_common_static_filter_values(static_filters, dynamic_filters);

		frm.set_value('filters_json', JSON.stringify(static_filters));
		frm.trigger('render_filters_table');
		frm.trigger('render_dynamic_filters_table');
	},

	is_standard: function(frm) {
		frm.trigger('render_dynamic_filters_table');
		frm.set_df_property("dynamic_filters_section", "hidden", 1);
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

	set_method_description: function(frm) {
		if (frm.doc.type == 'Custom') {
			frm.fields_dict.method.set_description(`
		Set the path to a whitelisted function that will return the number on the card in the format:
<pre class="small text-muted">
<code>
{
	"value": value,
	"fieldtype": "Currency"
}
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
				};
			});
		}

	},

	report_name: function(frm) {
		frm.filters = [];
		frm.set_value('filters_json', '{}');
		frm.set_value('dynamic_filters_json', '{}');
		frm.set_df_property('report_field', 'options', []);
		frm.trigger('set_report_filters');
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
		frm.set_value('filters_json', '[]');
		frm.set_value('dynamic_filters_json', '[]');
		frm.set_value('aggregate_function_based_on', '');
		frm.set_value('parent_document_type', '');
		frm.trigger('set_options');
		frm.trigger('set_parent_document_type');
	},

	set_options: function(frm) {
		if (frm.doc.type !== 'Document Type') {
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
			frm.trigger('render_dynamic_filters_table');
		}
	},

	set_report_filters: function(frm) {
		const report_name = frm.doc.report_name;
		if (report_name) {
			frappe.report_utils.get_report_filters(report_name).then(filters => {
				if (filters) {
					frm.filters = filters;
					const filter_values = frappe.report_utils.get_filter_values(filters);
					if (frm.doc.filters_json.length <= 2) {
						frm.set_value('filters_json', JSON.stringify(filter_values));
					}
				}
				frm.trigger('render_filters_table');
				frm.trigger('set_report_field_options');
				frm.trigger('render_dynamic_filters_table');
			});
		}
	},

	set_report_field_options: function(frm) {
		let filters = frm.doc.filters_json.length > 2 ? JSON.parse(frm.doc.filters_json) : null;
		if (frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2) {
			filters = frappe.dashboard_utils.get_all_filters(frm.doc);
		}
		frappe.xcall(
			'frappe.desk.query_report.run',
			{
				report_name: frm.doc.report_name,
				filters: filters,
				ignore_prepared_report: 1
			}
		).then(data => {
			if (data.result.length) {
				frm.field_options = frappe.report_utils.get_field_options_from_report(data.columns, data);
				frm.set_df_property('report_field', 'options', frm.field_options.numeric_fields);
				if (!frm.field_options.numeric_fields.length) {
					frappe.msgprint(__("Report has no numeric fields, please change the Report Name"));
				}
			} else {
				frappe.msgprint(__('Report has no data, please modify the filters or change the Report Name'));
			}
		});
	},

	render_filters_table: function(frm) {
		frm.set_df_property("filters_section", "hidden", 0);
		let is_document_type = frm.doc.type == 'Document Type';
		let is_dynamic_filter = f => ['Date', 'DateRange'].includes(f.fieldtype) && f.default;

		let wrapper = $(frm.get_field('filters_json').wrapper).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 20%">${__('Filter')}</th>
					<th style="width: 20%">${__('Condition')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.filters_json || '[]');
		let filters_set = false;

		// Set dynamic filters for reports
		if (frm.doc.type == 'Report') {
			let set_filters = false;
			frm.filters.forEach(f => {
				if (is_dynamic_filter(f)) {
					filters[f.fieldname] = f.default;
					set_filters = true;
				}
			});
			set_filters && frm.set_value('filters_json', JSON.stringify(filters));
		}

		let fields = [];
		if (is_document_type) {
			fields = [
				{
					fieldtype: 'HTML',
					fieldname: 'filter_area',
				}
			];

			if (filters.length) {
				filters.forEach(filter => {
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
		} else if (frm.filters.length) {
			fields = frm.filters.filter(f => f.fieldname);
			fields.map(f => {
				if (filters[f.fieldname]) {
					let condition = '=';
					const filter_row =
						$(`<tr>
							<td>${f.label}</td>
							<td>${condition}</td>
							<td>${filters[f.fieldname] || ""}</td>
						</tr>`);
					table.find('tbody').append(filter_row);
					if (!filters_set) filters_set = true;
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
					}
				},
				primary_action_label: "Set"
			});

			if (is_document_type) {
				frm.filter_group = new frappe.ui.FilterGroup({
					parent: dialog.get_field('filter_area').$wrapper,
					doctype: frm.doc.document_type,
					parent_doctype: frm.doc.parent_document_type,
					on_change: () => {},
				});
				filters && frm.filter_group.add_filters_to_filter_group(filters);
			}

			dialog.show();

			if (frm.doc.type == 'Report') {
				//Set query report object so that it can be used while fetching filter values in the report
				frappe.query_report = new frappe.views.QueryReport({'filters': dialog.fields_list});
				frappe.query_reports[frm.doc.report_name]
					&& frappe.query_reports[frm.doc.report_name].onload
						&& frappe.query_reports[frm.doc.report_name].onload(frappe.query_report);
			}

			dialog.set_values(filters);
		});

	},

	render_dynamic_filters_table(frm) {
		if (!frappe.boot.developer_mode || !frm.doc.is_standard || frm.doc.type == 'Custom') {
			return;
		}

		frm.set_df_property("dynamic_filters_section", "hidden", 0);

		let is_document_type = frm.doc.type == 'Document Type';

		let wrapper = $(frm.get_field('dynamic_filters_json').wrapper).empty();

		frm.dynamic_filter_table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 20%">${__('Filter')}</th>
					<th style="width: 20%">${__('Condition')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);

		frm.dynamic_filters = frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
			? JSON.parse(frm.doc.dynamic_filters_json)
			: null;

		frm.trigger('set_dynamic_filters_in_table');

		let filters = JSON.parse(frm.doc.filters_json || '[]');

		let fields = frappe.dashboard_utils.get_fields_for_dynamic_filter_dialog(
			is_document_type, filters, frm.dynamic_filters
		);

		frm.dynamic_filter_table.on('click', () => {
			let dialog = new frappe.ui.Dialog({
				title: __('Set Dynamic Filters'),
				fields: fields,
				primary_action: () => {
					let values = dialog.get_values();
					dialog.hide();
					let dynamic_filters = [];
					for (let key of Object.keys(values)) {
						if (is_document_type) {
							let [doctype, fieldname] = key.split(':');
							dynamic_filters.push([doctype, fieldname, '=', values[key]]);
						}
					}

					if (is_document_type) {
						frm.set_value('dynamic_filters_json', JSON.stringify(dynamic_filters));
					} else {
						frm.set_value('dynamic_filters_json', JSON.stringify(values));
					}
					frm.trigger('set_dynamic_filters_in_table');
				},
				primary_action_label: "Set"
			});

			dialog.show();
			dialog.set_values(frm.dynamic_filters);
		});
	},

	set_dynamic_filters_in_table: function(frm) {
		frm.dynamic_filters =  frm.doc.dynamic_filters_json && frm.doc.dynamic_filters_json.length > 2
			? JSON.parse(frm.doc.dynamic_filters_json)
			: null;

		if (!frm.dynamic_filters) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Dynamic Filters")}</td></tr>`);
			frm.dynamic_filter_table.find('tbody').html(filter_row);
		} else {
			let filter_rows = '';
			if ($.isArray(frm.dynamic_filters)) {
				frm.dynamic_filters.forEach(filter => {
					filter_rows +=
						`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`;
				});
			} else {
				let condition = '=';
				for (let [key, val] of Object.entries(frm.dynamic_filters)) {
					filter_rows +=
						`<tr>
							<td>${key}</td>
							<td>${condition}</td>
							<td>${val || ""}</td>
						</tr>`
					;
				}
			}

			frm.dynamic_filter_table.find('tbody').html(filter_rows);
		}
	},

	set_parent_document_type: async function(frm) {
		let document_type = frm.doc.document_type;
		let doc_is_table = document_type &&
			(await frappe.db.get_value('DocType', document_type, 'istable')).message.istable;

		frm.set_df_property('parent_document_type', 'hidden', !doc_is_table);

		if (document_type && doc_is_table) {
			let parent = await frappe.db.get_list('DocField', {
				filters: {
					'fieldtype': 'Table',
					'options': document_type
				},
				fields: ['parent']
			});

			parent && frm.set_query('parent_document_type', function() {
				return {
					filters: {
						"name": ['in', parent.map(({ parent }) => parent)]
					}
				};
			});

			if (parent.length === 1) {
				frm.set_value('parent_document_type', parent[0].parent);
			}
		}
	}

});
