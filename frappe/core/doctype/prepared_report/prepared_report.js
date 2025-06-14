// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Prepared Report", {
	render_filter_values: function (frm, filters) {
		var wrapper = $(frm.fields_dict["filter_values"].wrapper).empty();

		let filter_table = $(`<table class="table table-bordered">
			<thead>
				<tr>
					<td>${__("Filter")}</td>
					<td>${__("Value")}</td>
				</tr>
			</thead>
			<tbody></tbody>
		</table>`);

		Object.keys(filters).forEach((key) => {
			const filter_row = $(`<tr>
				<td>${frappe.model.unscrub(key)}</td>
				<td>${filters[key]}</td>
			</tr>`);
			filter_table.find("tbody").append(filter_row);
		});

		wrapper.append(filter_table);
	},

	refresh: function (frm) {
		frm.disable_save();

		const filters = JSON.parse(frm.doc.filters);
		if (!$.isEmptyObject(filters)) {
			frm.toggle_display(["filter_values"], 1);
			frm.events.render_filter_values(frm, filters);
		}

		// always keep report_name hidden - we do this as we can't set mandatory and hidden
		// property on a docfield at the same time
		frm.toggle_display(["report_name"], 0);

		if (frm.doc.status == "Completed") {
			frm.page.set_primary_action(__("Show Report"), () => {
				frappe.route_options = { prepared_report_name: frm.doc.name };
				frappe.set_route("query-report", frm.doc.report_name);
			});
			let csv_attached = (frm.get_files() || []).some((f) => f.file_url.endsWith(".csv"));
			if (!csv_attached) {
				frm.add_custom_button(__("Download as CSV"), function () {
					frappe.call({
						method: "frappe.core.doctype.prepared_report.prepared_report.enqueue_json_to_csv_conversion",
						args: {
							prepared_report_name: frm.doc.name,
						},
						callback: function () {
							frappe.msgprint(
								__(
									"Your CSV file is being generated and will appear in the Attachments section once ready. Additionally, you will get notified when the file is available for download."
								)
							);
						},
					});
				});
			}
		}
	},
});
