from __future__ import unicode_literals
import frappe

def execute():
	for file in frappe.db.sql("SELECT attached_to_name FROM tabFile WHERE attached_to_doctype = 'Communication'", as_dict=1):
		frappe.db.sql("UPDATE tabCommunication SET has_attachment = 1 WHERE name = %s", (file.attached_to_name))