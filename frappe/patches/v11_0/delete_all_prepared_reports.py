import frappe

def execute():
	prepared_reports = frappe.get_all("Prepared Report")
	for report in prepared_reports:
		frappe.delete_doc("Prepared Report", report.name)
