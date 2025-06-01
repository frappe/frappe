# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import nts
from nts.core.doctype.submission_queue.submission_queue import queue_submission
from nts.desk.form.load import run_onload
from nts.model.docstatus import DocStatus
from nts.monitor import add_data_to_monitor
from nts.utils.scheduler import is_scheduler_inactive
from nts.utils.telemetry import capture_doc


@nts.whitelist()
def savedocs(doc, action):
	"""save / submit / update doclist"""
	doc = nts.get_doc(json.loads(doc))
	capture_doc(doc, action)
	if doc.get("__islocal") and doc.name.startswith("new-" + doc.doctype.lower().replace(" ", "-")):
		# required to relink missing attachments if they exist.
		doc.__temporary_name = doc.name
	set_local_name(doc)

	# action
	doc.docstatus = {
		"Save": DocStatus.DRAFT,
		"Submit": DocStatus.SUBMITTED,
		"Update": DocStatus.SUBMITTED,
		"Cancel": DocStatus.CANCELLED,
	}[action]

	if doc.docstatus.is_submitted():
		if action == "Submit" and doc.meta.queue_in_background and not is_scheduler_inactive():
			queue_submission(doc, action)
			return
		doc.submit()
	else:
		doc.save()

	# update recent documents
	run_onload(doc)
	send_updated_docs(doc)

	add_data_to_monitor(doctype=doc.doctype, action=action)
	status_message = "Submitted" if doc.docstatus.is_submitted() else "Saved"
	nts.msgprint(nts._(status_message), indicator="green", alert=True)


@nts.whitelist()
def cancel(doctype=None, name=None, workflow_state_fieldname=None, workflow_state=None):
	"""cancel a doclist"""
	doc = nts.get_doc(doctype, name)
	capture_doc(doc, "Cancel")

	if workflow_state_fieldname and workflow_state:
		doc.set(workflow_state_fieldname, workflow_state)
	doc.cancel()
	send_updated_docs(doc)
	nts.msgprint(nts._("Cancelled"), indicator="red", alert=True)


def send_updated_docs(doc):
	from .load import get_docinfo

	get_docinfo(doc)

	d = doc.as_dict()
	if hasattr(doc, "localname"):
		d["localname"] = doc.localname

	nts.response.docs.append(d)


def set_local_name(doc):
	def _set_local_name(d):
		if doc.get("__islocal") or d.get("__islocal"):
			d.localname = d.name
			d.name = None

	_set_local_name(doc)
	for child in doc.get_all_children():
		_set_local_name(child)

	if doc.get("__newname"):
		doc.name = doc.get("__newname")
