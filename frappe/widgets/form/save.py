# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def savedocs():
	"""save / submit / update doclist"""
	try:
		wrapper = frappe.bean()
		wrapper.from_compressed(frappe.form_dict.docs, frappe.form_dict.docname)

		# action
		action = frappe.form_dict.action
		if action=='Update': action='update_after_submit'
		try:
			getattr(wrapper, action.lower())()
		except NameError, e:
			frappe.msgprint(frappe._("Name Exists"))
			raise

		# update recent documents
		frappe.user.update_recent(wrapper.doc.doctype, wrapper.doc.name)
		send_updated_docs(wrapper)

	except Exception, e:
		frappe.msgprint(frappe._('Did not save'))
		frappe.errprint(frappe.utils.get_traceback())
		raise

@frappe.whitelist()
def cancel(doctype=None, name=None):
	"""cancel a doclist"""
	try:
		wrapper = frappe.bean(doctype, name)
		wrapper.cancel()
		send_updated_docs(wrapper)
		
	except Exception, e:
		frappe.errprint(frappe.utils.get_traceback())
		frappe.msgprint(frappe._("Did not cancel"))
		raise
		
def send_updated_docs(wrapper):
	from load import get_docinfo
	get_docinfo(wrapper.doc.doctype, wrapper.doc.name)
	
	frappe.response['main_doc_name'] = wrapper.doc.name
	frappe.response['doctype'] = wrapper.doc.doctype
	frappe.response['docname'] = wrapper.doc.name
	frappe.response['docs'] = wrapper.doclist