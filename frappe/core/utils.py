# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe import _

def get_parent_doc(doc):
	"""Returns document of `reference_doctype`, `reference_doctype`"""
	if not hasattr(doc, "parent_doc"):
		if doc.reference_doctype and doc.reference_name:
			doc.parent_doc = frappe.get_doc(doc.reference_doctype, doc.reference_name)
		else:
			doc.parent_doc = None
	return doc.parent_doc

def set_timeline_doc(doc):
	"""Set timeline_doctype and timeline_name"""
	parent_doc = get_parent_doc(doc)
	if (doc.timeline_doctype and doc.timeline_name) or not parent_doc:
		return

	timeline_field = parent_doc.meta.timeline_field
	if not timeline_field:
		return

	doctype = parent_doc.meta.get_link_doctype(timeline_field)
	name = parent_doc.get(timeline_field)

	if doctype and name:
		doc.timeline_doctype = doctype
		doc.timeline_name = name

	else:	
		return