# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from rq import get_current_job
from rq.exceptions import NoSuchJobError
from rq.job import Job

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.monitor import add_data_to_monitor
from frappe.utils import now
from frappe.utils.background_jobs import get_redis_conn


class SubmissionQueueEntries(dict):
	def save(self):
		with open("./submission_queue_entries.json", "w+") as f:
			f.write(frappe.json.dumps(self, indent=4))


class SubmissionQueue(Document):
	@property
	def created_at(self):
		return self.creation

	@property
	def queued_doc(self):
		return getattr(self, "to_be_queued_doc", frappe.get_doc(self.ref_doctype, self.ref_docname))

	def __init__(self, *args, **kwargs):
		self.queue_entries = read_submission_queue_entries()
		super().__init__(*args, **kwargs)

	def insert(self, to_be_queued_doc: Document, action: str):
		self.to_be_queued_doc = to_be_queued_doc
		self.action_for_queuing = action
		super().insert()

	def lock(self):
		self.queued_doc.lock()

	def unlock(self):
		self.queued_doc.unlock()

	def after_insert(self):
		job = self.queue_action(
			"queue",
			to_be_queued_doc=self.queued_doc,
			action_for_queuing=self.action_for_queuing,
			timeout=600,
		)
		self.queue_entries[job.id] = {
			"DocType": self.ref_doctype,
			"Docname": self.ref_docname,
			"Status": job.get_status(refresh=True),
		}
		self.queue_entries.save()

		frappe.db.set_value(
			self.doctype,
			self.name,
			{"job_id": job.id},
			update_modified=False,
		)

	def queue(self, to_be_queued_doc: Document, action_for_queuing: str):
		_action = action_for_queuing.lower()
		job = get_current_job(connection=get_redis_conn())

		if _action == "update":
			_action = "submit"

		try:
			getattr(to_be_queued_doc, _action)()
			add_data_to_monitor(doctype=to_be_queued_doc.doctype, action=_action)
			values = {"status": "Finished"}
		except Exception:
			values = {"status": "Failed", "message": frappe.get_traceback()}
			frappe.db.rollback()

		values["ended_at"] = now()
		frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
		self.queue_entries[job.id] = {
			"DocType": to_be_queued_doc.doctype,
			"Docname": to_be_queued_doc.name,
			"Status": values["status"],
		}
		self.queue_entries.save()

		self.notify(values["status"], action_for_queuing)

	def notify(self, submission_status: str, action: str):
		if submission_status == "Failed":
			doctype = self.doctype
			docname = self.name
			message = _("Submission of {0} {1} with action {2} failed")
		else:
			doctype = self.ref_doctype
			docname = self.ref_docname
			message = _("Submission of {0} {1} with action {2} completed successfully")

		if self.enqueued_by == frappe.session.user:
			frappe.publish_realtime(
				"termination_status",
				{
					"message": message.format(
						frappe.bold(str(self.ref_doctype)), frappe.bold(self.ref_docname), frappe.bold(action)
					),
					"status": submission_status,
				},
			)
		else:
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

	@frappe.whitelist()
	def unlock_doc(self):
		if self.status != "Queued":
			return

		unlock_reference_doc(self.queued_doc, self.job_id, self.name)

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Submission Queue")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))


def read_submission_queue_entries():
	try:
		with open("./submission_queue_entries.json") as f:
			return SubmissionQueueEntries(frappe.json.loads(f.read()))
	except FileNotFoundError:
		with open("./submission_queue_entries.json", "w+") as f:
			f.write(frappe.json.dumps({}))
		return SubmissionQueueEntries()


def unlock_reference_doc(ref_doc: Document, job_id: str, submission_name: str):
	# TODO: If someone tries to unlock a previously failed job,
	# and someone else has already queued that document again
	# this will cause the queued document to be unlocked.

	try:
		job = Job.fetch(job_id, connection=get_redis_conn())
		status = job.get_status(refresh=True)
	except NoSuchJobError:
		# assuming the job failed here (?)
		status = "failed"

	# Checking if job is queue to be executed/executing
	if status in ("queued", "started"):
		frappe.msgprint(_("Document in queue for execution!"))

	# Checking any one of the possible termination statuses
	elif status in ("failed", "canceled", "stopped"):
		ref_doc.unlock()
		frappe.db.set_value(
			"Submission Queue", submission_name, "status", "Failed", update_modified=False
		)
		frappe.msgprint(_("Document Unlocked"))


def queue_submission(doc: Document, action: str):
	queue = frappe.new_doc("Submission Queue")
	queue.state = "Queued"
	queue.enqueued_by = frappe.session.user
	queue.ref_doctype = doc.doctype
	queue.ref_docname = doc.name
	queue.insert(doc, action)

	frappe.msgprint(
		_("Queued for Submission. You can track the progress over {0}.").format(
			f"<a href='/app/submission-queue/{queue.name}'><b>here</b></a>"
		),
		indicator="green",
		alert=True,
	)
