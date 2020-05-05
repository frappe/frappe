// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Website Analytics"] = {
	"filters": [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.now_date(true), -7),
		},
		{
			fieldname:"to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.now_date(true),
		},
		{
			fieldname: "range",
			label: __("Range"),
			fieldtype: "Select",
			options: [
				{ "value": "D", "label": __("Daily") },
				{ "value": "W", "label": __("Weekly") },
				{ "value": "M", "label": __("Monthly") },
			],
			default: "D",
			reqd: 1
		}
	]
};
