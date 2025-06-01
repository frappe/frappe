// Copyright (c) 2024, nts Technologies and contributors
// For license information, please see license.txt

nts.query_reports["Prepared Report Analytics"] = {
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
