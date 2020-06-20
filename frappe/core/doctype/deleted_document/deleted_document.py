# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe import _
import os
import shutil

class DeletedDocument(Document):
	pass

@frappe.whitelist()
def restore(name):
	deleted = frappe.get_doc('Deleted Document', name)
	data = json.loads(deleted.data)
	doc = frappe.get_doc(data)
	try:
		doc.insert()
		trash_path = frappe.utils.get_site_path('private/.trash/{}'.format(data.get('file_name')))
		if deleted.deleted_doctype == "File" and os.path.isfile(trash_path):
			shutil.move(trash_path, frappe.utils.get_files_path(data.get('file_name'), is_private=data.get('is_private')))

	except frappe.DocstatusTransitionError:
		frappe.msgprint(_("Cancelled Document restored as Draft"))
		doc.docstatus = 0
		doc.insert()

	doc.add_comment('Edit', _('restored {0} as {1}').format(deleted.deleted_name, doc.name))

	deleted.new_name = doc.name
	deleted.restored = 1
	deleted.db_update()

	frappe.msgprint(_('Document Restored'))
