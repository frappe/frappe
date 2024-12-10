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
			<tbody class="main-body"></tbody>
		</table>`);

		Object.entries(changes["from"]).forEach(([key, value]) => {
			if (Array.isArray(value || changes["to"][key])) {
				changes_table
					.find(".main-body")
					.append(frm.events.get_child_changes(key, value, changes["to"][key]));
			} else {
				changes_table.find("tbody").append(
					$(`<tr>
						<td>${frappe.model.unscrub(key)}</td>
						<td style="word-break: break-word" class="diff-remove">${changes["from"][key]}</td>
						<td style="word-break: break-word" class="diff-add">${changes["to"][key]}</td>
					</tr>`)
				);
			}
		});

		wrapper.append(changes_table);
	},

	get_child_changes: function (field_key, from, to) {
		let child_main = $(`<tr>
			<td>${frappe.model.unscrub(field_key)}</td>
			<td class="from"></td>
			<td class="to"></td>
		</tr>`);

		[from, to].forEach((val, index) => {
			if (!val) return;

			let for_value = index > 0 ? "to" : "frfromom";
			let child_table = $(`<table class="table-bordered small" style="margin-bottom: 5px">
				<tbody></tbody>
			</table>`);

			val.forEach((child_row) => {
				for (const [key, value] of Object.entries(child_row)) {
					child_table.find("tbody").append(
						$(
							`<tr>
							<td style="word-break: break-word">${frappe.model.unscrub(key)}</td>
							<td style="word-break: break-word">${value}</td>
						</tr>`
						)
					);
				}
			});

			child_main.find(`.${for_value}`).append(child_table);
		});

		return child_main;
	},
});
