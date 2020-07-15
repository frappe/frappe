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
		frm.trigger('render_filters_table');
		frm.trigger('render_dynamic_filters_table');
	},

	before_save: function(frm) {
		let dynamic_filters = JSON.parse(frm.doc.dynamic_filters_json || 'null');
		let static_filters = JSON.parse(frm.doc.filters_json || 'null');
		static_filters =
			frappe.dashboard_utils.remove_common_static_filter_values(static_filters, dynamic_filters);

		frm.set_value('filters_json', JSON.stringify(static_filters));
		frm.trigger('render_filters_table');
	},

	is_standard: function(frm) {
		if (frappe.boot.developer_mode && frm.doc.is_standard) {
			frm.trigger('render_dynamic_filters_table');
		} else {
			frm.set_df_property("dynamic_filters_section", "hidden", 1);
		}
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
		frm.trigger('set_options');
	},

	set_options: function(frm) {
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
		}
	},

	render_filters_table: function(frm) {
		frm.set_df_property("filters_section", "hidden", 0);

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

		frm.filters = JSON.parse(frm.doc.filters_json || '[]');

		set_filters_in_table(frm.filters, table);

		table.on('click', () => {
			let dialog = new frappe.ui.Dialog({
				title: __('Set Filters'),
				fields: [{
					fieldtype: 'HTML',
					fieldname: 'filter_area',
				}],
				primary_action: function() {
					let values = this.get_values();
					if (values) {
						this.hide();
						frm.filters = frm.filter_group.get_filters();
						frm.set_value('filters_json', JSON.stringify(frm.filters));
						set_filters_in_table(frm.filters, table);
						frm.trigger('render_dynamic_filters_table');
					}
				},
				primary_action_label: "Set"
			});

			frappe.dashboards.filters_dialog = dialog;

			frm.filter_group = new frappe.ui.FilterGroup({
				parent: dialog.get_field('filter_area').$wrapper,
				doctype: frm.doc.document_type,
				on_change: () => {},
			});

			frm.filter_group.add_filters_to_filter_group(frm.filters);

			dialog.show();
			dialog.set_values(frm.filters);
		});

	},

	render_dynamic_filters_table: function(frm) {
		if (!frappe.boot.developer_mode || !frm.doc.is_standard) {
			return;
		}
		let wrapper = $(frm.get_field('dynamic_filters_json').wrapper).empty();

		frm.set_df_property("dynamic_filters_section", "hidden", 0);

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

		frm.dynamic_filters = JSON.parse(frm.doc.dynamic_filters_json || '[]');

		set_filters_in_table(frm.dynamic_filters, table);

		let filters = JSON.parse(frm.doc.filters_json || '[]');
		let fields = [
			{
				fieldtype: 'HTML',
				fieldname: 'description',
				options:
					`<div>
						<p>Set dynamic filter values in JavaScript for the required fields here.
						</p>
						<p>Ex:
							<code>frappe.defaults.get_user_default("Company")</code>
						</p>
					</div>`
			}
		];

		if (frm.dynamic_filters.length) {
			filters = [...filters, ...frm.dynamic_filters];
		}

		filters.forEach(f => {
			for (let field of fields) {
				if (field.fieldname == f[0] + ':' + f[1]) {
					return;
				}
			}
			if (f[2] == '=') {
				fields.push({
					label: `${f[1]} (${f[0]})`,
					fieldname: f[0] + ':' + f[1],
					fieldtype: 'Data',
				});
			}
		});

		table.on('click', () => {
			let dialog = new frappe.ui.Dialog({
				title: __('Set Filters'),
				fields: fields,
				primary_action: () => {
					let values = dialog.get_values();
					if (values) {
						dialog.hide();
						let dynamic_filters = [];
						for (let key of Object.keys(values)) {
							let [doctype, fieldname] = key.split(':');
							dynamic_filters.push([doctype, fieldname, '=', values[key]]);
						}

						frm.set_value('dynamic_filters_json', JSON.stringify(dynamic_filters));
						frm.dynamic_filters = dynamic_filters;
						set_filters_in_table(frm.dynamic_filters, table);
					}
				},
				primary_action_label: "Set"
			});

			dialog.show();
			dialog.set_values(filters);
		});

	},

});

function set_filters_in_table(filters, table) {
	if (!filters.length) {
		const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
			${__("Click to Set Filters")}</td></tr>`);
		table.find('tbody').html(filter_row);
	} else {
		let filter_rows = '';
		filters.forEach(filter => {
			filter_rows +=
				`<tr>
					<td>${filter[1]}</td>
					<td>${filter[2] || ""}</td>
					<td>${filter[3]}</td>
				</tr>`;

		});
		table.find('tbody').html(filter_rows);
	}
}
