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
	
	for item in doc.items:
		for doctype in doc.prev_link_mapper:
			fieldname = doc.prev_link_mapper[doctype]["fieldname"]
			if item.as_dict()[fieldname]:
				flow_completion[doctype] = True
	
	for doctype in doctypes:
		if doctype not in flow_completion:
			links = get_linked_docs(frm_doctype, frm_docname, linkinfo, for_doctype=doctype)
			frappe.errprint(links)
			if links:
				flow_completion[doctype] = True
		
	return flow_completion