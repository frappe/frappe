# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe import _

# import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue


class SubmissionQueue(Document):
	...


def submit_in_background(doc: Document):
	try:
		doc.lock()
	except frappe.DocumentLockedError:
		frappe.throw(
			_("This document is currently queued for execution. Please try again"),
			title=_("Document Queued"),
			exc=frappe.DocumentLockedError,
		)
	new_queue = frappe.new_doc("Submission Queue")
	new_queue.state = "Queued"
	new_queue.start_time = datetime.now()
	new_queue.created_by = frappe.session.user
	new_queue.ref_doctype = doc.doctype
	new_queue.ref_docname = doc.name
	new_queue.insert()
	job = enqueue(_submit_in_background, name=new_queue.name, doc=doc)
	new_queue.job_id = job.id
	new_queue.save()


def _submit_in_background(name: str, doc: Document):
	doc.unlock()
	try:
		doc.submit()
		frappe.db.set_value("Submission Queue", name, {"state": "Submitted"})
	except Exception as e:
		frappe.db.set_value("Submission Queue", name, {"state": "Failed", "error": e})
