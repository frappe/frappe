// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Prepared Report', {
	refresh: function(frm) {
		frm.add_custom_button(__("Show Report"), function() {
			frappe.set_route(
				"query-report",
				frm.doc.report_name,
				frappe.utils.make_query_string({
					prepared_report_name: frm.doc.name
				})
			);
		});

		var wrapper = $(frm.fields_dict["filter_values"].wrapper);

		let filter_table = $(`<table class="table table-bordered">
			<thead>
				<tr>
					<td>${ __("Filter") }</td>
					<td>${ __("Value") }</td>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`);

		const filters = JSON.parse(JSON.parse(frm.doc.filters));

		Object.keys(filters).forEach(key => {
			const filter_row = $(`<tr>
				<td>${frappe.model.unscrub(key)}</td>
				<td>${filters[key]}</td>
			</tr>`);
			filter_table.find('tbody').append(filter_row);
		});

		wrapper.append(filter_table);
	}
});
