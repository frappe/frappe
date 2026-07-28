// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Postgres Index Suggestions"] = {
	filters: [
		{
			fieldname: "min_rows",
			label: __("Minimum Rows"),
			fieldtype: "Int",
			default: 10000,
		},
	],
};
