import frappe


def execute():
	"""
	Remove GSuite Template and GSuite Settings
	"""
	frappe.delete_doc_if_exists("DocType", "GSuite Settings")
	frappe.delete_doc_if_exists("DocType", "GSuite Templates")
