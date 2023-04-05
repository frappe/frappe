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
					<td>${__("Changed Value(s)")}</td>
					<td>${__("To")}</td>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`);

		Object.entries(changes["from"]).forEach(([key, value]) => {
			if (Array.isArray(value || changes["to"][key])) {
				let child_main = $(`<tr>
					<td>${frappe.model.unscrub(key)}</td>
					<td class="from"></td>
					<td class="to"></td>
				</tr>`);
				let html = {
					from: $(`<table class="table-bordered small">
					<tbody></tbody>
				</table>`),
					to: $(`<table class="table-bordered small">
					<tbody></tbody>
				</table>`),
				};

				[value, changes["to"][key]].forEach((val, index) => {
					let child_data = [];
					let for_value = index > 0 ? "to" : "from";

					val.forEach((k) => {
						child_data.push([Object.keys(k), Object.values(k)]);
					});
					child_data.forEach((k) => {
						if (k[0].length > 1) {
							// for multiple child fields
							let sub_child = $(`<tr>
								<td class="field"></td>
								<td class="value"></td>
							</tr>`);

							k[0].forEach((child, index) => {
								sub_child
									.find(".field")
									.append(
										$(
											`<tr><td style="word-break: break-word">${frappe.model.unscrub(
												child
											)}</td></tr>`
										)
									);
								sub_child
									.find(".value")
									.append(
										$(
											`<tr><td style="word-break: break-word">${k[1][index]}</td></tr>`
										)
									);
							});
							html[for_value].find("tbody").append(sub_child);
						} else {
							html[for_value].find("tbody").append(
								$(`<tr>
								<td style="word-break: break-word">${frappe.model.unscrub(k[0][0])}</td>
								<td style="word-break: break-word">${k[1][0]}</td>
							</tr>`)
							);
						}
					});
				});

				child_main.find(".from").append(html["from"]);
				child_main.find(".to").append(html["to"]);
				changes_table.find("tbody").append(child_main);
			} else {
				changes_table.find("tbody").append(
					$(`<tr>
				<td>${frappe.model.unscrub(key)}</td>
				<td style="word-break: break-word">${changes["from"][key]}</td>
				<td style="word-break: break-word">${changes["to"][key]}</td>
			</tr>`)
				);
			}
		});

		wrapper.append(changes_table);
	},
});
