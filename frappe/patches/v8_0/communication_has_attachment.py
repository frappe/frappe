from __future__ import unicode_literals
import frappe

def execute():
	for file in frappe.db.sql("select attached_to_name from tabFile where attached_to_doctype = 'Communication'",as_dict=1):
		frappe.db.sql("update tabCommunication set has_attachment = 1 where name = %s",(file.attached_to_name))