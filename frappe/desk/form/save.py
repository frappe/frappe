# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.desk.form.load import run_onload

@frappe.whitelist()
def savedocs():
	"""save / submit / update doclist"""
	try:
		doc = frappe.get_doc(json.loads(frappe.form_dict.doc))
		set_local_name(doc)

		# action
		doc.docstatus = {"Save":0, "Submit": 1, "Update": 1, "Cancel": 2}[frappe.form_dict.action]
		try:
			doc.save()
		except frappe.NameError, e:
			doctype, name, original_exception = e if isinstance(e, tuple) else (doc.doctype or "", doc.name or "", None)
			frappe.msgprint(frappe._("{0} {1} already exists").format(doctype, name))
			raise

		# update recent documents
		run_onload(doc)
		frappe.get_user().update_recent(doc.doctype, doc.name)
		send_updated_docs(doc)

	except Exception:
		frappe.msgprint(frappe._('Did not save'))
		frappe.errprint(frappe.utils.get_traceback())
		raise

@frappe.whitelist()
def cancel(doctype=None, name=None):
	"""cancel a doclist"""
	try:
		doc = frappe.get_doc(doctype, name)
		doc.cancel()
		send_updated_docs(doc)

	except Exception:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.msgprint(frappe._("Did not cancel"))
		raise

def send_updated_docs(doc):
	from load import get_docinfo
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
