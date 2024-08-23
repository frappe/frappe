import frappe


def execute():
	table = frappe.qb.DocType("Report")
	frappe.qb.update(table).set(table.prepared_report, 0).where(table.disable_prepared_report == 1)
