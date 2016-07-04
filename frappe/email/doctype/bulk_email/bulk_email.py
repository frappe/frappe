# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.model.document import Document

class BulkEmail(Document):
	pass

@frappe.whitelist()
def retry_sending(name):
	doc = frappe.get_doc("Bulk Email", name)
	if doc and doc.status == "Error":
		doc.status = "Not Sent"
		doc.save(ignore_permissions=True)

def on_doctype_update():
	"""Add index in `tabCommunication` for `(reference_doctype, reference_name)`"""
	frappe.db.add_index('Bulk Email', ('status', 'send_after', 'priority', 'creation'), 'index_bulk_flush')
