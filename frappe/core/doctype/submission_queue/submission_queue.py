# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from rq.exceptions import NoSuchJobError
from rq.job import Job

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.utils import now
from frappe.utils.background_jobs import get_redis_conn


class SubmissionQueue(Document):
	@property
	def created_at(self):
		return self.creation

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
			{"job_id": job.id},
			update_modified=False,
		)

	def queue_in_background(self, to_be_queued_doc: Document, action_for_queuing: str):
		_action = action_for_queuing.lower()

		if _action == "update":
			_action = "submit"

		try:
			getattr(to_be_queued_doc, _action)()
			values = {"status": "Finished"}
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
				f"<a href='/app/{str(self.ref_doctype).lower().replace(' ', '-')}/{str(self.ref_docname)}'><b>{str(self.ref_doctype)}</b></a>",
				frappe.bold(self.ref_docname),
				frappe.bold(action)
			),
		}

		notify_to = frappe.db.get_value("User", self.enqueued_by, fieldname="email")
		enqueue_create_notification([notify_to], notification_doc)

	def unlock_doc_and_update_status(self, doc_to_be_unlocked: Document, possible_status: tuple):
		try:
			job = Job(self.job_id, connection=get_redis_conn())
			status = job.get_status(refresh=True)
			if not status:
				raise NoSuchJobError

			if not doc_to_be_unlocked.is_locked:
				frappe.msgprint(_("Document is already unlocked updating status"))

			# Checking if job is queue to be executed
			if status == "queued":
				frappe.msgprint(_("Document in queue for execution!"))
				return

			# Checking any one of the possible termination statuses
			if status in possible_status:
				doc_to_be_unlocked.unlock()
				self.status = status.capitalize()
				self.save()
				frappe.msgprint(_("Document unlocked!"))

		except NoSuchJobError:
			# Need to update status
			doc_to_be_unlocked.unlock()
			frappe.msgprint(_("Unlocked document as no such document exists in queue"))

	@frappe.whitelist()
	def unlock_doc(self):
		possible_status = ("failed", "canceled", "stopped", "finished")
		doc_to_be_unlocked = frappe.get_doc(self.ref_doctype, self.ref_docname)
		self.unlock_doc_and_update_status(
			doc_to_be_unlocked=doc_to_be_unlocked, possible_status=possible_status
		)


def queue_submission(doc: Document, action: str):
	queue = frappe.new_doc("Submission Queue")
	queue.state = "Queued"
	queue.enqueued_by = frappe.session.user
	queue.ref_doctype = doc.doctype
	queue.ref_docname = doc.name
	queue.insert(doc, action)

	frappe.msgprint(
		frappe._("Queued for Submission. You can track the progress over {0}.").format(
			f"<a href='/app/submission-queue/{queue.name}'><b>here</b></a>"
		),
		indicator="green",
		alert=True,
	)
