// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Addresses And Contacts"] = {
	"filters": [
		{
			"reqd": 1,
			"fieldname":"party_type",
			"label": __("Party Type"),
			"fieldtype": "Link",
			"options": "DocType",
			"get_query": function() {
				return {
					"filters": {
						"name": ["in","Customer,Supplier,Sales Partner"],
					}
				}
			},
			"default": "Customer"
		},
		{
			"fieldname":"party_name",
			"label": __("Party Name"),
			"fieldtype": "Dynamic Link",
			"get_options": function() {
				var party_type = frappe.query_report_filters_by_name.party_type.get_value();
				if(!party_type) {
					frappe.throw(__("Please select Party Type first"));
				}
				return party_type;
			}
		}
	]
}
