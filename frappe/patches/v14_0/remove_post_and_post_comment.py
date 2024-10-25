import frappe


def execute() -> None:
	frappe.delete_doc_if_exists("DocType", "Post")
	frappe.delete_doc_if_exists("DocType", "Post Comment")
