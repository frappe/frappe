import json

import frappe


def execute():
	if not frappe.db.table_exists("Dashboard Chart"):
		return

	charts_to_modify = frappe.get_all(
		"Dashboard Chart",
		fields=["name", "filters_json", "document_type"],
		filters={"chart_type": ["not in", ["Report", "Custom"]]},
	)

	for chart in charts_to_modify:
		old_filters = frappe.parse_json(chart.filters_json)

		if chart.filters_json and isinstance(old_filters, dict):
			new_filters = []
			doctype = chart.document_type

			for key in old_filters.keys():
				filter_value = old_filters[key]
				if isinstance(filter_value, list):
					new_filters.append([doctype, key, filter_value[0], filter_value[1], 0])
				else:
					new_filters.append([doctype, key, "=", filter_value, 0])

			new_filters_json = json.dumps(new_filters)
			frappe.db.set_value("Dashboard Chart", chart.name, "filters_json", new_filters_json)
