import frappe


def execute():
	frappe.db.change_column_type("SMS Parameter", "value", "varchar(255)")
