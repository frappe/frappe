// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Number Card', {
	refresh: function(frm) {
		frm.set_df_property("filters_section", "hidden", 1);
		frm.trigger('set_options');
		frm.trigger('render_filters_table');

		if (frm.doc.type == 'Custom') {
			if (!frappe.boot.developer_mode) {
				frm.disable_form();
			}
			frm.trigger('set_filters_description');
		}
	},

	set_filters_description: function(frm) {
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
	},

	type: function(frm) {
		frm.trigger('render_filters_table');
	},

	filters_config: function(frm) {
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

		const is_custom = frm.doc.type == 'Custom';
		let fields;
		if (!is_custom) {
			fields = [{
				fieldtype: 'HTML',
				fieldname: 'filter_area',
			}];
			frm.filters = JSON.parse(frm.doc.filters_json || 'null');
		} else {
			fields = eval(frm.doc.filters_config);
			frm.filters = JSON.parse(frm.doc.filters_json || '{}');
		}

		let wrapper = $(frm.get_field('filters_json').wrapper).empty();
		frm.filter_table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 33%">${__('Filter')}</th>
					<th style="width: 33%">${__('Condition')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);

		frm.trigger('set_filters_in_table');

		frm.filter_table.on('click', () => {
			let dialog = new frappe.ui.Dialog({
				title: __('Set Filters'),
				fields: fields,
				primary_action: function() {
					let values = this.get_values();
					if (values) {
						this.hide();
						frm.filters = is_custom ? values: frm.filter_group.get_filters();
						frm.set_value('filters_json', JSON.stringify(frm.filters));
						frm.trigger('set_filters_in_table');
					}
				},
				primary_action_label: "Set"
			});

			frm.filters_dialog = dialog;
			if (!is_custom) {
				frm.trigger('create_filter_group');
			}

			dialog.show();
			dialog.set_values(frm.filters);
		});

	},

	create_filter_group: function(frm) {
		frm.filter_group = new frappe.ui.FilterGroup({
			parent: frm.filters_dialog.get_field('filter_area').$wrapper,
			doctype: frm.doc.document_type,
			on_change: () => {},
		});

		frm.filters && frm.filter_group.add_filters_to_filter_group(frm.filters);
	},

	set_filters_in_table: function(frm) {
		if (!frm.filters) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("Click to Set Filters")}</td></tr>`);
			frm.filter_table.find('tbody').html(filter_row);
		} else {
			let filter_rows = '';

			if (frm.doc.type !== 'Custom') {
				frm.filters.forEach(filter => {
					filter_rows +=
						`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`;
				});
			} else {
				let fields = eval(frm.doc.filters_config);
				fields.map(f => {
					if (frm.filters[f.fieldname]) {
						let condition = '=';
						filter_rows +=
							`<tr>
								<td>${f.label}</td>
								<td>${condition}</td>
								<td>${frm.filters[f.fieldname] || ""}</td>
							</tr>`;
					}
				});
			}
			frm.filter_table.find('tbody').html(filter_rows);
		}
	}
});
