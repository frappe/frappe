// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["User Doctype Permissions"] = {
	filters: [
		{
			fieldname: "user",
			label: __("User"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "doctype",
			label: __("Doctype"),
			fieldtype: "Link",
			options: "DocType",
		},
	],
	onload(report) {
		const refresh = report.refresh.bind(report);
		report.refresh = function () {
			const user = report.get_filter_value("user");
			const doctype = report.get_filter_value("doctype");
			if (!user && !doctype) {
				report.toggle_message(true, __("Please set at least one filter: User or DocType"));
				report.toggle_report(false);
				return;
			}
			return refresh();
		};
	},
};
