# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import cint


class BulkUpdate(Document):
	pass

@frappe.whitelist()
def update(doctype, field, value, condition='', limit=500):
	if not limit or cint(limit) > 500:
		limit = 500

	if condition:
		condition = ' where ' + condition

	if ';' in condition:
		frappe.throw(_('; not allowed in condition'))

	docnames = frappe.db.sql_list(
		'''select name from `tab{0}`{1} limit {2} offset 0'''.format(doctype, condition, limit)
	)
	data = {}
	data[field] = value
	return submit_cancel_or_update_docs(doctype, docnames, 'update', data)

@frappe.whitelist()
def submit_cancel_or_update_docs(doctype, docnames, action='submit', data=None):
	docnames = frappe.parse_json(docnames)

	if data:
		data = frappe.parse_json(data)

	failed = bulk_update(doctype, docnames, action, data)

	return failed

def show_progress(docnames, message, i, description):
	n = len(docnames)
	if n >= 10:
		frappe.publish_progress(
			float(i) * 100 / n,
			title = message,
			description = description
		)

def check_enqueue_action(doctype, action) -> bool:
	doc = frappe.db.get_list("Enqueue Selected Action", fields=["*"])
	for d in doc:
		if d.document_type == doctype:
			if action == "submit" and d.submit_action == 1:
				return True
			if action == "cancel" and d.cancel_action == 1:
				return True
			if action == "delete" and d.delete_action == 1:
				return True
			if action == "rename" and d.rename_action == 1:
				return True
	return False


def bulk_update(doctype, docnames, action, data=None):
	failed = []
	i = 0
	enqueue_action = check_enqueue_action(doctype, action)

	if enqueue_action:
		lock_document(doctype, docnames, action)
		frappe.msgprint("Running a background job to {0} document's".format(action))

	for i, d in enumerate(docnames, 1):
		doc = frappe.get_doc(doctype, d)

		try:
			message = ''
			if action == 'submit' and doc.docstatus.is_draft():
				doc.submit()
				message = _('Submiting {0}').format(doctype)
			elif action == 'cancel' and doc.docstatus.is_submitted():
				doc.cancel()
				message = _('Cancelling {0}').format(doctype)
			elif action == 'update' and not doc.docstatus.is_cancelled():
				doc.update(data)
				doc.save()
				message = _('Updating {0}').format(doctype)
			elif action == 'submit' and doc.docstatus.is_locked():
				job_name = "{0}-{1}-{2}".format(doctype, d, "submit")
				frappe.enqueue(doc.submit, job_name=job_name)
			elif action == 'cancel' and doc.docstatus.is_locked():
				job_name = "{0}-{1}-{2}".format(doctype, d, "cancel")
				frappe.enqueue(doc.cancel,job_name=job_name)
			else:
				failed.append(d)

		except Exception:
			failed.append(d)
			frappe.db.rollback()

		if not enqueue_action:
			show_progress(docnames, message, i, d)

	return failed

def lock_document(doctype, docnames, action):
	for d in docnames:
		doc = frappe.get_doc(doctype, d)
		if doc.docstatus == 2 and action == 'submit':
			frappe.throw("Cannot submit cancelled document {0}".format(d))
		elif doc.docstatus == 1 and action == 'delete':
			frappe.throw("Cannot delete submitted document. please cancel it first {0}".format(d))
		elif doc.docstatus == 1 and action == 'submit':
			frappe.throw("Cannot resumbit a submitted document {0}".format(d))
		elif doc.docstatus == 0 and action == 'cancel':
			frappe.throw("Cannot cancel document {0}".format(d))
		doc.lock_doc()