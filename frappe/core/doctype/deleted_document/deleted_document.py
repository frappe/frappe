# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.desk.doctype.bulk_update.bulk_update import show_progress
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name


class DeletedDocument(Document):
	pass

	@staticmethod
	def clear_old_logs(days=180):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Deleted Document")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))


@frappe.whitelist()
def restore(name, alert=True):
	deleted = frappe.get_doc("Deleted Document", name)

	if deleted.restored:
		frappe.throw(_("Document {0} Already Restored").format(name), exc=frappe.DocumentAlreadyRestored)

	doc = frappe.get_doc(json.loads(deleted.data))

	try:
		doc.insert()
	except frappe.DocstatusTransitionError:
		frappe.msgprint(_("Cancelled Document restored as Draft"))
		doc.docstatus = 0
		active_workflow = get_workflow_name(doc.doctype)
		if active_workflow:
			workflow_state_fieldname = frappe.get_value("Workflow", active_workflow, "workflow_state_field")
			if doc.get(workflow_state_fieldname):
				doc.set(workflow_state_fieldname, None)
		doc.insert()

	doc.add_comment("Edit", _("restored {0} as {1}").format(deleted.deleted_name, doc.name))

	deleted.new_name = doc.name
	deleted.restored = 1
	deleted.db_update()

	if alert:
		frappe.msgprint(_("Document Restored"))


@frappe.whitelist()
def bulk_restore(docnames):
	docnames = frappe.parse_json(docnames)
	message = _("Restoring Deleted Document")
	restored, invalid, failed = [], [], []

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
			frappe.message_log.pop()
			failed.append(d)
			frappe.db.rollback()

	return {"restored": restored, "invalid": invalid, "failed": failed}
