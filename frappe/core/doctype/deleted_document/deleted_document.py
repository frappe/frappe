# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.desk.doctype.bulk_update.bulk_update import show_progress
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name


class DeletedDocument(Document):
	_DOCTYPE_NAME = "Deleted Document"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data: DF.Code | None
		deleted_doctype: DF.Data | None
		deleted_name: DF.Data | None
		new_name: DF.ReadOnly | None
		restored: DF.Check
	# end: auto-generated types

	no_feed_on_delete = True

	@staticmethod
	def clear_old_logs(days=180):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Deleted Document")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@frappe.whitelist()
def restore(name: str | int, alert: bool = True):
	frappe.only_for("System Manager")
	deleted = frappe.get_doc("Deleted Document", name)

	if deleted.restored:
		frappe.throw(_("Document {0} Already Restored").format(name), exc=frappe.DocumentAlreadyRestored)

	doc = frappe.get_doc(json.loads(deleted.data))

	if not frappe.has_permission(doc.doctype, "create"):
		frappe.throw(
			_("You do not have permission to create or restore documents of type {0}.").format(doc.doctype),
			frappe.PermissionError,
		)

	if not frappe.has_permission(doc.doctype, "read", doc=doc):
		frappe.throw(_("You do not have permission to restore this document."), frappe.PermissionError)

	original_owner = doc.get("owner")
	original_creation = doc.get("creation")
	original_modified = doc.get("modified")
	original_modified_by = doc.get("modified_by")
	doc.flags.from_restore = True
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

	# retain original metadata
	frappe.db.set_value(
		doc.doctype,
		doc.name,
		{
			"owner": original_owner,
			"creation": original_creation,
			"modified": original_modified,
			"modified_by": original_modified_by,
		},
		update_modified=False,
	)

	doc.add_comment("Edit", _("restored {0} as {1}").format(deleted.deleted_name, doc.name))

	deleted.new_name = doc.name
	deleted.restored = 1
	deleted.db_update()

	if alert:
		frappe.msgprint(_("Document Restored"))


@frappe.whitelist()
def bulk_restore(docnames: str | list[str]):
	frappe.only_for("System Manager")
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
			frappe.clear_last_message()
			invalid.append(d)

		except Exception:
			frappe.clear_last_message()
			failed.append(d)
			frappe.db.rollback()

	return {"restored": restored, "invalid": invalid, "failed": failed}
