# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe, json

@frappe.whitelist()
def savedocs():
	"""save / submit / update doclist"""
	try:
		doc = frappe.get_doc(json.loads(frappe.form_dict.doc))

		# action
		doc.docstatus = {"Save":0, "Submit": 1, "Update": 1, "Cancel": 2}[frappe.form_dict.action]
		try:
			doc.save()
		except NameError, e:
			frappe.msgprint(frappe._("Name Exists"))
			raise

		# update recent documents
		frappe.user.update_recent(doc.doctype, doc.name)
		send_updated_docs(doc)

	except Exception, e:
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
		
	except Exception, e:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.msgprint(frappe._("Did not cancel"))
		raise
		
def send_updated_docs(doc):
	from load import get_docinfo
	get_docinfo(doc.doctype, doc.name)
	
	d = doc.as_dict()
	d["localname"] = doc.localname
	
	frappe.response.docs.append(d)