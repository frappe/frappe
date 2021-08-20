import frappe

def get_data():
	return frappe._dict({
		"dashboards": get_dashboards(),
		"charts": get_charts(),
		"number_cards": None,
	})

def get_dashboards():
	return [{
		"name": "Website",
		"dashboard_name": "Website",
		"charts": [
			{ "chart": "Website Analytics", "width": "Full" }
		]
	}]

def get_charts():
	return [{
		"chart_name": "Website Analytics",
		"chart_type": "Report",
		"custom_options": "{\"type\": \"line\", \"lineOptions\": {\"regionFill\": 1}, \"axisOptions\": {\"shortenYAxisNumbers\": 1}, \"tooltipOptions\": {}}",
		"doctype": "Dashboard Chart",
		"filters_json": "{}",
		"group_by_type": "Count",
		"is_custom": 1,
		"is_public": 1,
		"name": "Website Analytics",
		"number_of_groups": 0,
		"report_name": "Website Analytics",
		"time_interval": "Yearly",
		"timeseries": 0,
		"timespan": "Last Year",
		"type": "Line"
	}]