# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
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

	items = frappe.db.sql_list('''select name from `tab{0}`{1} limit 0, {2}'''.format(doctype,
		condition, limit), debug=1)
	update_and_save(doctype, items, field, value)

@frappe.whitelist()
def update_items(doctype, field, value, items):
	items = frappe.utils.get_json(items)
	n = len(items)
	if not n: return
	update_and_save(doctype, items, field, value)

def update_and_save(doctype, items, field, value):
	n = len(items)
	for i, d in enumerate(items, 1):
		doc = frappe.get_doc(doctype, d)
		doc.set(field, value)

		try:
			doc.save()
		except Exception as e:
			frappe.msgprint(_("Validation failed for {0}").format(frappe.bold(doc.name)))
		#show progress if there are 10 or more items
		if n >= 10:
			frappe.publish_progress(float(i)*100/n, title = _('Updating Records'))
	frappe.clear_messages()
	frappe.msgprint(_('{0} record(s) updated').format(n), title=_('Success'), indicator='green')

@frappe.whitelist()
def submit_items(doctype, items):
	items = frappe.utils.get_json(items)
	n = len(items)
	for i, d in enumerate(items, 1):
		doc = frappe.get_doc(doctype, d)
		
		try:
			doc.submit()
		except Exception as e:
			frappe.msgprint(_("Cannot submit {0}").format(frappe.bold(doc.name)))
			raise e
		#show progress if there are 10 or more items
		if n >= 10:
			frappe.publish_progress(float(i)*100/n, title = _('Submiting Records'))
	frappe.clear_messages()
	frappe.msgprint(_('{0} record(s) submitted').format(n), title=_('Success'), indicator='green')

@frappe.whitelist()
def cancel_items(doctype, items):
	items = frappe.utils.get_json(items)
	n = len(items)
	for i, d in enumerate(items, 1):
		doc = frappe.get_doc(doctype, d)
		
		try:
			doc.cancel()
		except Exception as e:
			frappe.msgprint(_("Cannot cancel {0}").format(frappe.bold(doc.name)))
			raise e
		#show progress if there are 10 or more items
		if n >= 10:
			frappe.publish_progress(float(i)*100/n, title = _('Cancelling Records'))
	frappe.clear_messages()
	frappe.msgprint(_('{0} record(s) cancelled').format(n), title=_('Success'), indicator='green')

