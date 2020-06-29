// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Exponential Smoothing Forecast"] = {
	"filters": [
		{
			"fieldname":"forecast_template",
			"label": __("Forecast Template"),
			"fieldtype": "Link",
			"options": "Forecast Template",
			"reqd": 1
		},
		{
			"fieldname":"document_type",
			"label": __("Document Type"),
			"fieldtype": "Data",
			"read_only": 1,
		},
		{
			"fieldname":"based_on",
			"label": __("Forecasting Based On"),
			"fieldtype": "Data",
			"read_only": 1,
		},
	]
};
