"""
Run this after updating country_info.json and or
"""
import frappe


def execute():
	for col in ("field", "doctype"):
		frappe.db.sql_ddl(f"alter table `tabSingles` modify column `{col}` varchar(255)")
