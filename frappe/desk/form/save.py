# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from frappe.desk.form.load import run_onload
from frappe.model.docstatus import DocStatus
from frappe.monitor import add_data_to_monitor
from frappe.utils.scheduler import is_scheduler_inactive
from frappe.utils.telemetry import capture_doc


@frappe.whitelist()
def savedocs(doc, action) -> None:
	"""save / submit / update doclist"""
	doc = frappe.get_doc(json.loads(doc))
	capture_doc(doc, action)
	if doc.get("__islocal") and doc.name.startswith("new-" + doc.doctype.lower().replace(" ", "-")):
		# required to relink missing attachments if they exist.
		doc.__temporary_name = doc.name
	set_local_name(doc)

	# action
	doc.docstatus = {
		"Save": DocStatus.draft(),
		"Submit": DocStatus.submitted(),
		"Update": DocStatus.submitted(),
		"Cancel": DocStatus.cancelled(),
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
	frappe.msgprint(frappe._("Saved"), indicator="green", alert=True)


@frappe.whitelist()
def cancel(doctype=None, name=None, workflow_state_fieldname=None, workflow_state=None) -> None:
	"""cancel a doclist"""
	doc = frappe.get_doc(doctype, name)
	capture_doc(doc, "Cancel")

	if workflow_state_fieldname and workflow_state:
		doc.set(workflow_state_fieldname, workflow_state)
	doc.cancel()
	send_updated_docs(doc)
	frappe.msgprint(frappe._("Cancelled"), indicator="red", alert=True)


@frappe.whitelist()
def discard(doctype: str, name: str | int) -> None:
	"""discard a draft document"""
	doc = frappe.get_doc(doctype, name)
	capture_doc(doc, "Discard")

	doc.discard()
	send_updated_docs(doc)
	frappe.msgprint(frappe._("Discarded"), indicator="red", alert=True)


def send_updated_docs(doc) -> None:
	from .load import get_docinfo

	get_docinfo(doc)

	d = doc.as_dict()
	if hasattr(doc, "localname"):
		d["localname"] = doc.localname

	frappe.response.docs.append(d)


def set_local_name(doc) -> None:
	def _set_local_name(d) -> None:
		if doc.get("__islocal") or d.get("__islocal"):
			d.localname = d.name
			d.name = None

	_set_local_name(doc)
	for child in doc.get_all_children():
		_set_local_name(child)

	if doc.get("__newname"):
		doc.name = doc.get("__newname")
