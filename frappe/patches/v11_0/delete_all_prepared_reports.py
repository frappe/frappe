import frappe


def execute():
	if frappe.db.table_exists("Prepared Report"):
		frappe.reload_doc("core", "doctype", "prepared_report")
		prepared_reports = frappe.get_all("Prepared Report")
		for report in prepared_reports:
			frappe.delete_doc("Prepared Report", report.name)
