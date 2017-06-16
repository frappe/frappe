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
	n = len(items)

	for i, d in enumerate(items):
		doc = frappe.get_doc(doctype, d)
		doc.set(field, value)

		try:
			doc.save()
		except Exception as e:
			frappe.msgprint(_("Validation failed for {0}").format(frappe.bold(doc.name)))
			raise e

		frappe.publish_progress(float(i)*100/n,
			title = _('Updating Records'), doctype='Bulk Update', docname='Bulk Update')

	# clear messages
	frappe.local.message_log = []
	frappe.msgprint(_('{0} records updated').format(n), title=_('Success'), indicator='green')