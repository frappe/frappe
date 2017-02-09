// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Feedback Ratings"] = {
	"filters": [
		{
			"fieldname": "party_type",
			"label": __("Party Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"reqd": 1,
			"default": "Issue"
		},
		{
			"fieldname": "party_name",
			"label": __("Party"),
			"fieldtype": "Dynamic Link",
			"get_options": function() {
				var party_type = frappe.query_report_filters_by_name.party_type.get_value();
				if(!party_type) {
					frappe.throw(__("Please select Party Type first"));
				}
				return party_type;
			}
		},
		{ 
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			'reqd': 1,
			"default": frappe.datetime.add_days(frappe.datetime.nowdate(), -30)
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			'reqd': 1,
			"default":frappe.datetime.nowdate()
		}
	],

	get_chart_data: function(columns, result) {
		return {
			data: {
				x: 'Date',
				columns: [
					['Date'].concat($.map(result, function(d) { return d[0]; })),
					['Average Feedback'].concat($.map(result, function(d) { return d[1]; }))
				]
			},
			chart_type: 'line',

		}
	}
}
