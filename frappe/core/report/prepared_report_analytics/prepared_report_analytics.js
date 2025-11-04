// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Prepared Report Analytics"] = {
	filters: [
		{
			fieldname: "report",
			label: __("Report"),
			fieldtype: "Data",
		},
		{
			fieldname: "top_10",
			label: __("Top 10"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "in_minutes",
			label: __("In Minutes"),
			fieldtype: "Check",
			default: 0,
		},
	],
};
