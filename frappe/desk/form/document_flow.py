# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import json
from frappe.desk.form.linked_with import get_linked_docs, get_linked_doctypes

@frappe.whitelist()
def get_document_completion_status(doctypes, frm_doctype, frm_docname):
	if isinstance(doctypes, basestring):
		doctypes = json.loads(doctypes)
	
	doc = frappe.get_doc(frm_doctype, frm_docname)
	linkinfo = get_linked_doctypes(frm_doctype)
	
	flow_completion = {}
	
	if hasattr(doc, "prev_link_mapper"):
		for doctype in doc.prev_link_mapper:
			fieldname = doc.prev_link_mapper[doctype]["fieldname"]
			lookup_doctype = doc.prev_link_mapper[doctype]["doctype"]
			limit = doc.prev_link_mapper[doctype].get("limit") or 1
			condition = make_condition(doc.prev_link_mapper[doctype].get("filters"))
			
			if condition:
				condition = "where {condition}".format(condition=condition)
			else:
				condition = ""

			result = frappe.db.sql_list("select {fieldname} from `tab{doctype}` \
				{condition} limit {limit}".format(fieldname=fieldname, doctype=lookup_doctype,
				condition=condition, limit=limit))

			if result:
				flow_completion[doctype] = True

	for doctype in doctypes:
		if doctype not in flow_completion:
			links = get_linked_docs(frm_doctype, frm_docname, linkinfo, for_doctype=doctype)
			if links:
				flow_completion[doctype] = True

	return flow_completion

def make_condition(filters=None):
	condition = []
	if filters and isinstance(filters, list):
		for cond in filters:
			condition.append("`tab{0}`.{1} {2} '{3}'".format(*cond))
	
	return " and ".join(condition)
		