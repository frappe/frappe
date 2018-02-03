# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.email.queue import send_one
from frappe.limits import get_limits
from frappe.utils import now_datetime


class EmailQueue(Document):
	def set_recipients(self, recipients):
		self.set("recipients", [])
		for r in recipients:
			self.append("recipients", {"recipient":r, "status":"Not Sent"})

	def on_trash(self):
		self.prevent_email_queue_delete()

	def prevent_email_queue_delete(self):
		'''If email limit is set, don't allow users to delete Email Queue record'''
		if get_limits().emails and frappe.session.user != 'Administrator':
			frappe.throw(_('Only Administrator can delete Email Queue'))

	def get_duplicate(self, recipients):
		values = self.as_dict()
		del values['name']
		duplicate = frappe.get_doc(values)
		duplicate.set_recipients(recipients)
		return duplicate

@frappe.whitelist()
def retry_sending(name):
	doc = frappe.get_doc("Email Queue", name)
	if doc and (doc.status == "Error" or doc.status == "Partially Errored"):
		doc.status = "Not Sent"
		for d in doc.recipients:
			if d.status != 'Sent':
				d.status = 'Not Sent'
		doc.save(ignore_permissions=True)

@frappe.whitelist()
def send_now(name):
	send_one(name, now=True)

def on_doctype_update():
	"""Add index in `tabCommunication` for `(reference_doctype, reference_name)`"""
	frappe.db.add_index('Email Queue', ('status', 'send_after', 'priority', 'creation'), 'index_bulk_flush')
