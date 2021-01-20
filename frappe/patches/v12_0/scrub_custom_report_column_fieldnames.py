import frappe

def execute():
	reports = frappe.get_all('Report',
		fields = ['name', 'json'],
		filters = {
			'is_standard': 'No',
			'report_type': ['!=', 'Report Builder'],
		})

	for report in reports:
		columns = frappe.parse_json(report.json)
		if columns:
			for col in columns:
				if isinstance(col, dict) and col.get("fieldname"):
					col['fieldname'] = frappe.scrub(col['fieldname'])
			frappe.db.set_value('Report', report.name, 'json', frappe.as_json(columns))
