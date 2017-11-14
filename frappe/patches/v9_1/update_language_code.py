import frappe

def execute():
	frappe.rename_doc("Language", "sr", 'sr-RS', force=True)
	frappe.rename_doc("Language", "sr-SP", 'sr', force=True)
