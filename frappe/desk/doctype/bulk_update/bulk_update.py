# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils.deprecations import deprecated
from frappe.utils.scheduler import is_scheduler_inactive


class BulkUpdate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		condition: DF.SmallText | None
		document_type: DF.Link
		field: DF.Literal[None]
		limit: DF.Int
		update_value: DF.SmallText

	# end: auto-generated types

	@frappe.whitelist()
	def bulk_update(self):
		self.check_permission("write")
		limit = self.limit if self.limit and cint(self.limit) < 500 else 500
		query_args = {"doctype": self.document_type, "limit": limit, "pluck": "name"}
		if self.condition:
			try:
				filters = frappe.parse_json(self.condition)
				if isinstance(filters, dict):
					if "or_filters" in filters:
						query_args["or_filters"] = filters.pop("or_filters")
				query_args["filters"] = filters
			except Exception as e:
				frappe.throw(_("The Bulk Update could not happen due to <b>{0}</b>").format(str(e)))

		docnames = frappe.get_all(**query_args)
		return submit_cancel_or_update_docs(
			self.document_type, docnames, "update", {self.field: self.update_value}
		)


@frappe.whitelist()
def submit_cancel_or_update_docs(doctype, docnames, action="submit", data=None, task_id=None):
	if isinstance(docnames, str):
		docnames = frappe.parse_json(docnames)

	if len(docnames) < 20:
		return _bulk_action(doctype, docnames, action, data, task_id)
	elif len(docnames) <= 500:
		frappe.msgprint(_("Bulk operation is enqueued in background."), alert=True)
		frappe.enqueue(
			_bulk_action,
			doctype=doctype,
			docnames=docnames,
			action=action,
			data=data,
			task_id=task_id,
			queue="short",
			timeout=1000,
		)
	else:
		frappe.throw(_("Bulk operations only support up to 500 documents."), title=_("Too Many Documents"))


def _bulk_action(doctype, docnames, action, data, task_id=None):
	if data:
		data = frappe.parse_json(data)

	failed = []
	num_documents = len(docnames)

	for idx, docname in enumerate(docnames, 1):
		doc = frappe.get_doc(doctype, docname)
		try:
			message = ""
			if action == "submit" and doc.docstatus.is_draft():
				if doc.meta.queue_in_background and not is_scheduler_inactive():
					queue_submission(doc, action)
					message = _("Queuing {0} for Submission").format(doctype)
				else:
					doc.submit()
					message = _("Submitting {0}").format(doctype)
			elif action == "cancel" and doc.docstatus.is_submitted():
				doc.cancel()
				message = _("Cancelling {0}").format(doctype)
			elif action == "update" and not doc.docstatus.is_cancelled():
				doc.update(data)
				doc.save()
				message = _("Updating {0}").format(doctype)
			else:
				failed.append(docname)
			frappe.db.commit()
			frappe.publish_progress(
				percent=idx / num_documents * 100,
				title=message,
				description=docname,
				task_id=task_id,
			)

		except Exception:
			frappe.log_error("Bulk action failed")
			failed.append(docname)
			frappe.db.rollback()

	return failed


@deprecated
def show_progress(docnames, message, i, description):
	n = len(docnames)
	frappe.publish_progress(float(i) * 100 / n, title=message, description=description)
