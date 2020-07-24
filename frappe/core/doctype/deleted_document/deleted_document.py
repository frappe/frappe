# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.desk.doctype.bulk_update.bulk_update import show_progress
from frappe.model.document import Document
from frappe import _


class DeletedDocument(Document):
	pass


@frappe.whitelist()
def restore(name, alert=True):
	deleted = frappe.get_doc('Deleted Document', name)

	if deleted.restored:
		frappe.throw(_("Document {0} Already Restored").format(name), exc=frappe.DocumentAlreadyRestored)

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
	message = _('Restoring Deleted Document')
	restored = []
	invalid = []
	failed = []

	for i, d in enumerate(docnames):
		try:
			show_progress(docnames, message, i + 1, d)
			restore(d, alert=False)
			frappe.db.commit()
			restored.append(d)

		except frappe.DocumentAlreadyRestored:
			frappe.message_log.pop()
			invalid.append(d)

		except Exception:
			failed.append(d)
			frappe.db.rollback()
			frappe.message_log.pop()

	if failed or invalid:
		tail = "</ul>"

		restored_data = ""
		restored_head = _("Documents restored successfully") + "<br><ul>"
		for docname in restored:
			restored_data += "<li><a href='/desk#Form/Deleted Document/{0}'>{0}</a></li>".format(docname)
		restored_body = restored_head + restored_data + tail

		invalid_data = ""
		invalid_head = _("Documents that were already Restored") + "<br><ul>"
		for docname in invalid:
			invalid_data += "<li><a href='/desk#Form/Deleted Document/{0}'>{0}</a></li>".format(docname)
		invalid_body = invalid_head + invalid_data + tail

		failed_data = ""
		failed_head = _("Documents that Failed to Restore") + "<br><ul>"
		for docname in failed:
			failed_data += "<li><a href='/desk#Form/Deleted Document/{0}'>{0}</a></li>".format(docname)
		failed_body = failed_head + failed_data + tail

		summary = (restored_body if restored else "") + (invalid_body if invalid else "") + (failed_body if failed else "")
		frappe.msgprint(summary, title="Document Restoration Summary", indicator="orange", is_minimizable=True)

	return restored
