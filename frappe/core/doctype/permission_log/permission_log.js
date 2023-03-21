// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Permission Log", {
	refresh: function (frm) {
		frm.events.render_changed_values(frm);
	},

	render_changed_values: function (frm) {
		let wrapper = $(frm.fields_dict["changed_values"].wrapper).empty();
		const changes = JSON.parse(frm.doc.changes);
		let changes_table = $(`<table class="table table-bordered">
			<thead>
				<tr>
					<td>${__("Field")}</td>
					<td>${__("Value")}</td>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`);

		Object.keys(changes).forEach((key) => {
			changes_table.find("tbody").append(
				$(`<tr>
			<td>${frappe.model.unscrub(key)}</td>
			<td>${changes[key]}</td>
		</tr>`)
			);
		});

		wrapper.append(changes_table);
	},
});
