import frappe


def execute():
	frappe.delete_doc_if_exists("DocType", "Web View")
	frappe.delete_doc_if_exists("DocType", "Web View Component")
	frappe.delete_doc_if_exists("DocType", "CSS Class")
