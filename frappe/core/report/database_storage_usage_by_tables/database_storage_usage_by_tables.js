// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Database Storage Usage By Tables"] = {
	filters: [],
	onload: function (report) {
		report.page.add_inner_button(
			__("Optimize"),
			function () {
				let d = new frappe.ui.Dialog({
					title: "Optimize Doctype",
					fields: [
						{
							label: "Select a DocType",
							fieldname: "doctype_name",
							fieldtype: "Link",
							options: "DocType",
							get_query: function () {
								return {
									filters: { issingle: ["=", false], is_virtual: ["=", false] },
								};
							},
						},
					],
					size: "small",
					primary_action_label: "Optimize",
					primary_action(values) {
						frappe.call({
							method: "frappe.core.report.database_storage_usage_by_tables.database_storage_usage_by_tables.optimize_doctype",
							args: {
								doctype_name: values.doctype_name,
							},
							callback: function (r) {
								if (!r.exec) {
									frappe.msgprint({
										title: __("Success"),
										message: __("Table optimized successfully"),
										indicator: "green",
									});
								}
							},
						});
						d.hide();
					},
				});
				d.show();
			},
			__("Actions")
		);
	},
};
