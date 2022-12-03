# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from urllib.parse import quote

from rq import get_current_job
from rq.exceptions import NoSuchJobError
from rq.job import Job

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.monitor import add_data_to_monitor
from frappe.utils import now, time_diff_in_seconds
from frappe.utils.background_jobs import get_redis_conn
from frappe.utils.data import cint


class SubmissionQueue(Document):
	@property
	def created_at(self):
		return self.creation

	@property
	def enqueued_by(self):
		return self.owner

	@property
	def queued_doc(self):
		return getattr(self, "to_be_queued_doc", frappe.get_doc(self.ref_doctype, self.ref_docname))

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Submission Queue")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))

	def insert(self, to_be_queued_doc: Document, action: str):
		self.to_be_queued_doc = to_be_queued_doc
		self.action_for_queuing = action
		super().insert(ignore_permissions=True)

	def lock(self):
		self.queued_doc.lock()

	def unlock(self):
		self.queued_doc.unlock()

	def update_job_id(self, job_id):
		frappe.db.set_value(
			self.doctype,
			self.name,
			{"job_id": job_id},
			update_modified=False,
		)
		frappe.db.commit()

	def after_insert(self):
		self.queue_action(
			"background_submission",
			to_be_queued_doc=self.queued_doc,
			action_for_queuing=self.action_for_queuing,
			timeout=600,
			enqueue_after_commit=True,
		)

	def background_submission(self, to_be_queued_doc: Document, action_for_queuing: str):
		if self.status == "Failed":
			# If the document has already been unlocked by _unlock_reference_doc
			return
		# Set the job id for that submission doctyp
		self.update_job_id(get_current_job().id)
		_action = action_for_queuing.lower()
		if _action == "update":
			_action = "submit"

		try:
			getattr(to_be_queued_doc, _action)()
			add_data_to_monitor(
				doctype=to_be_queued_doc.doctype,
				docname=to_be_queued_doc.name,
				action=_action,
				execution_time=time_diff_in_seconds(now(), self.created_at),
				enqueued_by=self.enqueued_by,
			)
			values = {"status": "Finished"}
		except Exception:
			values = {"status": "Failed", "exception": frappe.get_traceback()}
			frappe.db.rollback()

		values["ended_at"] = now()
		frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
		self.notify(values["status"], action_for_queuing)

	def notify(self, submission_status: str, action: str):
		message = _("Action {0} run on {1} {2} ")
		if submission_status == "Failed":
			doctype = self.doctype
			docname = self.name
			message += "failed"
		else:
			doctype = self.ref_doctype
			docname = self.ref_docname
			message += "finished"

		message = message.format(
			frappe.bold(action),
			frappe.bold(str(self.ref_doctype)),
			frappe.bold(self.ref_docname),
		)
		time_diff = time_diff_in_seconds(now(), self.created_at)
		if cint(time_diff) <= 60:
			frappe.publish_realtime(
				"msgprint",
				{
					"message": message
					+ f". View it <a href='/app/{quote(doctype.lower().replace(' ', '-'))}/{quote(docname)}'><b>here</b></a>",
					"alert": True,
					"indicator": "red" if submission_status == "Failed" else "green",
				},
				user=self.enqueued_by,
			)
		else:
			notification_doc = {
				"type": "Alert",
				"document_type": doctype,
				"document_name": docname,
				"subject": message,
			}

			notify_to = frappe.db.get_value("User", self.enqueued_by, fieldname="email")
			enqueue_create_notification([notify_to], notification_doc)

	def _unlock_reference_doc(self):
		try:
			job = Job.fetch(self.job_id, connection=get_redis_conn())
			status = job.get_status(refresh=True)
			exc = job.exc_info
		except NoSuchJobError:
			exc = None
			status = "failed"

		if status in ("queued", "started"):
			frappe.msgprint(_("Document in queue for execution!"))
			return

		self.queued_doc.unlock()
		values = (
			{"status": "Finished"} if status == "finished" else {"status": "Failed", "exception": exc}
		)
		frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
		frappe.msgprint(_("Document Unlocked"))

	@frappe.whitelist()
	def unlock_doc(self):
		# NOTE: this can lead to some weird unlocking/locking behaviours.
		# for example: hitting unlock on a submission could lead to unlocking of another submission
		# of the same reference document.
		if self.status != "Queued":
			return

		self._unlock_reference_doc()


def queue_submission(doc: Document, action: str, alert: bool = True):
	queue = frappe.new_doc("Submission Queue")
	queue.status = "Queued"
	queue.ref_doctype = doc.doctype
	queue.ref_docname = doc.name
	queue.insert(doc, action)

	if alert:
		frappe.msgprint(
			_("Queued for Submission. You can track the progress over {0}.").format(
				f"<a href='/app/submission-queue/{queue.name}'><b>here</b></a>"
			),
			indicator="green",
			alert=True,
		)


def format_tb(traceback: str):
	traceback = traceback.strip().split("\n")[-1]
	if len(traceback.split()) > 6:
		return " ".join(traceback.split()[0:6]) + "..."
	return traceback


@frappe.whitelist()
def get_latest_submissions(doctype, docname):
	# NOTE: not used creation as orderby intentianlly as we have used update_modified=False everywhere
	# hence assuming modified will be equal to creation for submission queue documents

	dt = "Submission Queue"
	out = {}

	filters = {"ref_doctype": doctype, "ref_docname": docname}
	failed_submission = frappe.db.get_value(
		dt, filters=filters | {"status": "Failed"}, fieldname=["name", "exception"]
	)
	latest_submission = frappe.db.get_value(dt, filters=filters, fieldname=["name", "status"])

	if failed_submission:
		out["latest_failed_submission"], out["latest_failed_submission_exc_info"] = (
			failed_submission[0],
			format_tb(failed_submission[1]),
		)

	if latest_submission:
		out["latest_submission"], out["latest_submission_status"] = latest_submission

	return out
