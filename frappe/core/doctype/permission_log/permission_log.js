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
					<td>${__("From")}</td>
					<td>${__("To")}</td>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`);

		Object.keys(changes["from"]).forEach((key) => {
			changes_table.find("tbody").append(
				$(`<tr>
			<td>${frappe.model.unscrub(key)}</td>
			<td style="word-break: break-all">${JSON.stringify(changes["from"][key], null, 1)}</td>
			<td style="word-break: break-all">${JSON.stringify(changes["to"][key], null, 1)}</td>
		</tr>`)
			);
		});

		wrapper.append(changes_table);
	},
});
