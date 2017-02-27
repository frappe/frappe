// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Feedback Ratings"] = {
	"filters": [
		{
			"fieldname": "document_type",
			"label": __("Document Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"reqd": 1,
			"default": "Issue",
			"get_query": function() {
				return {
					"query": "frappe.core.report.feedback_ratings.feedback_ratings.get_document_type"
				}
			}
		},
		{
			"fieldname": "document_id",
			"label": __("Document ID"),
			"fieldtype": "Dynamic Link",
			"get_options": function() {
				var document_type = frappe.query_report_filters_by_name.document_type.get_value();
				if(!document_type) {
					frappe.throw(__("Please select Document Type first"));
				}
				return document_type;
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
