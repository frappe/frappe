import frappe


def execute():
	"""Remove stale docfields from legacy version"""
	frappe.db.delete("DocField", {"options": "Data Import", "parent": "Data Import Legacy"})
