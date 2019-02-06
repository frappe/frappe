// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dashboard Chart', {
	onload: function(frm) {
		var wrapper = $(frm.fields_dict["filters_json"].wrapper).empty();
		let filter_table = $(`<table class="table table-bordered">
			<thead>
				<tr>
					<td>${ __("Filter") }</td>
					<td>${ __("Value") }</td>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`);

		const filters = JSON.parse(frm.doc.filters_json);

		Object.keys(filters).forEach(key => {
			const filter_row = $(`<tr>
				<td>${frappe.model.unscrub(key)}</td>
				<td>${filters[key]}</td>
			</tr>`);
			filter_table.find('tbody').append(filter_row);
		});

		wrapper.append(filter_table);
	},
	refresh: function(frm) {

	}
});
