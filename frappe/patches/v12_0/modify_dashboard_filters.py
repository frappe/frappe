import frappe
import json

# This patch modifies existing dashboard chart filters
# This will convert `filters_json` field to array

def execute():
	dashboard_charts = frappe.db.sql('''select name, document_type, filters_json from `tabDashboard chart`''', as_dict=1)
	if dashboard_charts:
		for item in dashboard_charts:
			filters_json = json.loads(item.filters_json)
			if filters_json and isinstance(filters_json, dict):
				keys = filters_json.keys()
				new_filters_json = []
				for key in keys:
					new_filters_json.append([item.document_type, key, '=', filters_json[key], 0])
				frappe.db.set_value('Dashboard Chart', item.name, 'filters_json', json.dumps(new_filters_json))
