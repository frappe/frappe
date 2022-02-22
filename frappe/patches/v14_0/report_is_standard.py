import frappe


def execute():
	report = frappe.qb.DocType("Report")
	frappe.qb.update(report).set(report.is_standard, 1).where(
		report.is_standard == "Yes"
	)
	frappe.qb.update(report).set(report.is_standard, 0).where(
		report.is_standard == "No"
	)
