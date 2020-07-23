# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.desk.doctype.bulk_update.bulk_update import show_progress
from frappe.model.document import Document
from frappe import _

class DeletedDocument(Document):
	pass

@frappe.whitelist()
def restore(name, alert=True):
	deleted = frappe.get_doc('Deleted Document', name)

	if deleted.restored:
		frappe.throw(_("Document {0} Already Restored".format(name)), exc=frappe.DocumentAlreadyRestored)

	doc = frappe.get_doc(json.loads(deleted.data))

	try:
		doc.insert()
	except frappe.DocstatusTransitionError:
		frappe.msgprint(_("Cancelled Document restored as Draft"))
		doc.docstatus = 0
		doc.insert()

	doc.add_comment('Edit', _('restored {0} as {1}').format(deleted.deleted_name, doc.name))

	deleted.new_name = doc.name
	deleted.restored = 1
	deleted.db_update()

	if alert:
		frappe.msgprint(_('Document Restored'))


@frappe.whitelist()
def bulk_restore(docnames):
	docnames = frappe.parse_json(docnames)
	doctype = "Deleted Document"
	restored = []
	failed = []

	for i, d in enumerate(docnames):
		try:
			restore(d, alert=False)
			message = _('Restoring {0}').format(doctype)
			frappe.db.commit()
			show_progress(docnames, message, i+1, d)
			restored.append(d)
		except frappe.DocumentAlreadyRestored:
			failed.append(d)
		except Exception as e:
			failed.append(d)
			frappe.db.rollback()

	return restored