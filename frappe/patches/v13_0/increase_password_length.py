import frappe


def execute():
	frappe.db.change_column_type(table="__Auth", column="password", type="TEXT")
