# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe import _

class DeletedDocument(Document):
	pass

@frappe.whitelist()
def restore(name):
	deleted = frappe.get_doc('Deleted Document', name)
	doc = frappe.get_doc(json.loads(deleted.data))
	try:
		doc.insert()
	except frappe.DocstatusTransitionError:
		frappe.throw(_("Cannot restore Cancelled Document"))

	doc.add_comment('Edit', _('restored {0} as {1}').format(deleted.deleted_name, doc.name))

	deleted.new_name = doc.name
	deleted.restored = 1
	deleted.db_update()

	frappe.msgprint(_('Document Restored'))