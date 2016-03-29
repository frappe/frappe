# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.model.document import Document
from frappe.email.bulk import send_one

class BulkEmail(Document):
	pass

@frappe.whitelist()
def retry_sending(name):
	doc = frappe.get_doc("Bulk Email", name)
	if doc and doc.status == "Error":
		doc.status = "Not Sent"
		doc.save(ignore_permissions=True)

@frappe.whitelist()
def send_now(name):
	doc = frappe.get_doc("Bulk Email", name)
	send_one(doc, now=True)