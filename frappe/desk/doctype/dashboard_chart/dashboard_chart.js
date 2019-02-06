// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt
frappe.provide("frappe.dashboard_chart_sources");

frappe.ui.form.on('Dashboard Chart', {
	refresh: function(frm) {
		frm.trigger("show_filters");
	},

	source: function(frm) {
		frm.trigger("show_filters");
	},

	show_filters: function(frm) {
		if (frm.doc.source) {
			if (frappe.dashboard_chart_sources && frappe.dashboard_chart_sources[frm.doc.source]) {
				frm.trigger('render_filters_table');
			} else {
				frappe.call({
					method: 'frappe.core.page.dashboard.dashboard.get_script',
					args: {
						source_name: frm.doc.source
					},
					callback: result => {
						frappe.dom.eval(result.message.script || '');
						frm.trigger('render_filters_table');
					}
				});
			}
		}
	},

	render_filters_table: function(frm) {
		let fields = frappe.dashboard_chart_sources[frm.doc.source].filters;

		let wrapper = $(frm.get_field('filters_json').wrapper).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
			<thead>
				<tr>
					<th>${__('Filter')}</th>
					<th>${__('Value')}</th>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(wrapper);
		$(`<p class="text-muted small">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(frm.doc.filters_json || '{}');
		fields.map( f => {
			const filter_row = $(`<tr><td>${f.label}</td><td>${filters[f.fieldname]}</td></tr>`);
			table.find('tbody').append(filter_row);
		});

		table.on('click', () => {
			let dialog = new frappe.ui.Dialog({
				title: __('Set Filters'),
				fields: fields,
				primary_action: function() {
					let values = this.get_values();
					if(values) {
						this.hide();
						frm.set_value('filters_json', JSON.stringify(values));
						frm.trigger('show_filters');
					}
				}
			});
			dialog.show();
			dialog.set_values(filters);
		});
	}
});


