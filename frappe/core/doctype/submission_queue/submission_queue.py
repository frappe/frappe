# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document


class SubmissionQueue(Document):
	def insert(self, to_be_queued_doc: Document, action: str):
		self.to_be_queued_doc = to_be_queued_doc
		self.action_for_queuing = action
		super().insert()

	def queue_action(self, action, **kwargs):
		from frappe.utils.background_jobs import enqueue

		try:
			self.to_be_queued_doc.lock()
		except frappe.DocumentLockedError:
			frappe.throw(
				_("Docuement is already queued for execution"),
				title=_("Documenet Queued"),
				exc=frappe.DocumentLockedError
			)
		return enqueue(
			"frappe.model.document.execute_action",
			__doctype=self.to_be_queued_doc,
			__name=self.to_be_queued_doc.name,
			__action=action,
			**kwargs
		)

	def after_insert(self):
		job = self.queue_action(
			"queue_in_background",
			to_be_queued_doc=self.to_be_queued_doc,
			action_for_queuing=self.action_for_queuing,
		)
		frappe.db.set_value(self.doctype, self.name, {"job_id": job.id}, update_modified=False)


	def queue_in_background(self, to_be_queued_doc: Document, action_for_queuing: str):
		_action = action_for_queuing.lower()

		if _action == "update":
			_action = "submit"

		try:
			getattr(to_be_queued_doc, _action)()
			values = {"status": "Completed"}
		except Exception as e:
			values = {"status": "Failed", "message": str(e)}

		frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
		notify(name=self.name)


def notify(name: str):
	notification_doc =  {
			"type": "Notification",
			"document_type": "Submission Queue",
			"document_name": name,
			"subject": "Job Queued",
			"from_user": frappe.session.user,
			"email_content": "Hello",
		}

	mention = frappe.db.get_value("User", filters=frappe.db.get_value(
		"Submission Queue", filters=name, fieldname="created_by"
	), fieldname="email")
	if mention:
		enqueue_create_notification([mention], notification_doc)


def queue_submission(doc: Document, action: str):
	queue = frappe.new_doc("Submission Queue")
	queue.state = "Queued"
	queue.start_time = datetime.now()
	queue.created_by = frappe.session.user
	queue.ref_doctype = doc.doctype
	queue.ref_docname = doc.name
	queue.insert(doc, action)
