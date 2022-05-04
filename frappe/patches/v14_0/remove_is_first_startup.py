import frappe


def execute():
	frappe.db.sql(
		"""DELETE FROM `tabSingles` where doctype = 'System Settings' and field = 'is_first_startup'"""
	)
