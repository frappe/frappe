import frappe


def execute():
	frappe.reload_doc("core", "doctype", "document_naming_rule")
