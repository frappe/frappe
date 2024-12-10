"""
Run this after updating country_info.json and or
"""
<<<<<<< HEAD
=======

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
import frappe


def execute():
	for col in ("field", "doctype"):
		frappe.db.sql_ddl(f"alter table `tabSingles` modify column `{col}` varchar(255)")
