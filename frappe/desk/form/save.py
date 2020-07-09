# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.desk.form.load import run_onload

@frappe.whitelist()
def savedocs(doc, action):
	"""save / submit / update doclist"""
	try:
		doc = frappe.get_doc(json.loads(doc))
		set_local_name(doc)

		# action
		doc.docstatus = {"Save":0, "Submit": 1, "Update": 1, "Cancel": 2}[action]

		if doc.docstatus==1:
			doc.submit()
		else:
			doc.save()

		# update recent documents
		run_onload(doc)
		send_updated_docs(doc)
	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		raise

@frappe.whitelist()
def cancel(doctype=None, name=None, workflow_state_fieldname=None, workflow_state=None):
	"""cancel a doclist"""
	try:
		doc = frappe.get_doc(doctype, name)
		if workflow_state_fieldname and workflow_state:
			doc.set(workflow_state_fieldname, workflow_state)
		doc.cancel()
		send_updated_docs(doc)

	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.msgprint(frappe._("Did not cancel"))
		raise

def send_updated_docs(doc):
	from .load import get_docinfo
	get_docinfo(doc)

	d = doc.as_dict()
	if hasattr(doc, 'localname'):
		d["localname"] = doc.localname

	frappe.response.docs.append(d)

def set_local_name(doc):
	def _set_local_name(d):
		if doc.get('__islocal') or d.get('__islocal'):
			d.localname = d.name
			d.name = None

	_set_local_name(doc)
	for child in doc.get_all_children():
		_set_local_name(child)

	if doc.get("__newname"):
		doc.name = doc.get("__newname")
