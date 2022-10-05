# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.utils import now


class SubmissionQueue(Document):
	def insert(self, to_be_queued_doc: Document, action: str):
		self.to_be_queued_doc = to_be_queued_doc
		self.action_for_queuing = action
		super().insert()

	def lock(self):
		self.to_be_queued_doc.lock()

	def unlock(self):
		# NOTE: this is called in execute_action method of Document class
		# where get_doc is called hence we lose the to_be_queued_doc attribute
		frappe.get_doc(self.ref_doctype, self.ref_docname).unlock()

	def after_insert(self):
		job = self.queue_action(
			"queue_in_background",
			to_be_queued_doc=self.to_be_queued_doc,
			action_for_queuing=self.action_for_queuing,
			timeout=600,
		)
		frappe.db.set_value(
			self.doctype,
			self.name,
			{"job_id": job.id, "enqueued_at": now()},
			update_modified=False,
		)

	def queue_in_background(self, to_be_queued_doc: Document, action_for_queuing: str):
		_action = action_for_queuing.lower()

		if _action == "update":
			_action = "submit"

		try:
			getattr(to_be_queued_doc, _action)()
			values = {"status": "Completed"}
		except Exception:
			values = {"status": "Failed", "message": frappe.get_traceback()}
			frappe.db.rollback()

		values["ended_at"] = now()
		frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
		self.notify(values["status"], action_for_queuing)

	def notify(self, submission_status: str, action: str):
		if submission_status == "Failed":
			doctype = "Submission Queue"
			docname = self.name
			message = _("Submission of {0} {1} with action {2} failed")
		else:
			doctype = self.ref_doctype
			docname = self.ref_docname
			message = _("Submission of {0} {1} with action {2} completed successfully")

		notification_doc = {
			"type": "Alert",
			"document_type": doctype,
			"document_name": docname,
			"subject": message.format(
				frappe.bold(str(self.ref_doctype)), frappe.bold(self.ref_docname), frappe.bold(action)
			),
		}

		notify_to = frappe.db.get_value("User", self.enqueued_by, fieldname="email")
		enqueue_create_notification([notify_to], notification_doc)


def queue_submission(doc: Document, action: str):
	queue = frappe.new_doc("Submission Queue")
	queue.state = "Queued"
	queue.enqueued_by = frappe.session.user
	queue.ref_doctype = doc.doctype
	queue.ref_docname = doc.name
	queue.insert(doc, action)

	return queue.name
