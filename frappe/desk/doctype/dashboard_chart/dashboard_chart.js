// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.provide('frappe.dashboards.chart_sources');
frappe.require('assets/frappe/js/frappe/ui/filters/filter.js');

frappe.ui.form.on('Dashboard Chart', {
	setup: function(frm) {
		// fetch timeseries from source
		frm.add_fetch('source', 'timeseries', 'timeseries');
	},

	refresh: function(frm) {
		frm.chart_filters = null;
		frm.set_df_property("filters_section", "hidden", 1);
		frm.trigger('update_options');
		let wrapper = $(frm.get_field('filter_html').wrapper).empty();
		wrapper.append('<div class="filter-edit-area"></div>');
	},

	source: function(frm) {
		frm.trigger("show_filters");
	},

	chart_type: function(frm) {
		// set timeseries based on chart type
		if (['Count', 'Average', 'Sum'].includes(frm.doc.chart_type)) {
			frm.set_value('timeseries', 1);
		}
		frm.set_value('document_type', '');
	},

	document_type: function(frm) {
		// update `based_on` options based on date / datetime fields
		frm.set_value('source', '');
		frm.set_value('based_on', '');
		frm.set_value('value_based_on', '');
		frm.set_value('filters_json', '[]');
		frm.trigger('update_options');
	},

	update_options: function(frm) {
		let doctype = frm.doc.document_type;
		let date_fields = [
			{ label: __('Created On'), value: 'creation' },
			{ label: __('Last Modified On'), value: 'modified' }
		];
		let value_fields = [];
		let update_form = function() {
			// update select options
			frm.set_df_property('based_on', 'options', date_fields);
			frm.set_df_property('value_based_on', 'options', value_fields);
			frm.trigger("show_filters");
		}


		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				// get all date and datetime fields
				frappe.get_meta(doctype).fields.map(df => {
					if (['Date', 'Datetime'].includes(df.fieldtype)) {
						date_fields.push({ label: df.label, value: df.fieldname });
					}
					if (['Int', 'Float', 'Currency', 'Percent'].includes(df.fieldtype)) {
						value_fields.push({ label: df.label, value: df.fieldname });
					}
				});
				update_form();
				frappe.meta.docfield_list[doctype] = frappe.get_meta(doctype).fields;
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
			if (frm.doc.chart_type === 'Custom') {
				if (frm.doc.source) {
					frappe.xcall('frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config', { name: frm.doc.source })
						.then(config => {
							frappe.dom.eval(config);
							frm.chart_filters = frappe.dashboards.chart_sources[frm.doc.source].filters;
							frm.trigger('render_filters_table');
						});
				} else {
					frm.chart_filters = [];
					frm.trigger('render_filters_table');
				}
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
		// let fields = frm.chart_filters;

		let wrapper = $(frm.get_field('filters_json').wrapper).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th style="width: 50%">${__('Filter')}</th>
					<th>${__('Condition')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.filters_json || '[]');
		var filters_set = false;

		if (filters) {
			filters.map((f, index) => {
				const filter_row = $(`<tr data-id="${index}"><td>${f[1]}</td><td>${f[2]}</td><td>${f[3]}</td></tr>`);
				table.find('tbody').append(filter_row);
				filters_set = true;
			});
		}

		if (!filters_set) {
			const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
				${__("No filters added")}</td></tr>`);
			table.find('tbody').append(filter_row);
		} else {
			$(`<p class="text-muted small">${__("Click on the row to edit filter")}</p>`).appendTo(wrapper);
		}

		table.find('tr').click(function() {
			let index = $(this).attr('data-id');
			if (filters[index]) {
				frm.events.show_filter(frm, filters[index][1], filters[index][2], filters[index][3], false, index);
			}
		});
	},
	filters_fn: function(frm) {
		// sending default fieldname as name
		frm.events.show_filter(frm, 'name', '=', undefined, true, 0);
	},
	add_filter: function(frm) {
		frm.trigger('filters_fn');
	},
	show_filter(frm, fieldname, condition, value, is_new, index) {
		let list_filter = new frappe.ui.Filter({
			parent: $(frm.get_field('filter_html').wrapper),
			parent_doctype: frm.doc.document_type,
			fieldname: fieldname,
			hidden: false,
			condition: condition,
			doctype: frm.doc.document_type,
			value: value,
			remove: function() {
				if (is_new == false) {
					// to delete filter from array
					let arr = JSON.parse(frm.doc.filters_json);
					arr.splice(parseInt(index), 1);
					frm.set_value('filters_json', JSON.stringify(arr));
					frm.trigger('show_filters');
				}
				this.filter_edit_area.remove();
			},
			on_change: function() {
				let val = list_filter.get_value();
				if (val[2] == 'like' || val[2] == 'Like')
					val[3] = val[3].replace(/%/g, "");
				let arr = JSON.parse(frm.doc.filters_json);
				if (is_new == false) {
					arr[index] = val;
				} else {
					arr.push(val);
				}
				frm.set_value('filters_json', JSON.stringify(arr));
				frm.trigger('show_filters');
			}
		});
	}
});