from __future__ import unicode_literals
import frappe


def execute():
	files = frappe.get_all("File", filters={"attached_to_doctype": "Prepared Report", "is_private": 0})
	for file_name in files:
		file_doc = frappe.get_doc("File", file_name)
		file_doc.is_private = 1
		file_doc.save()
