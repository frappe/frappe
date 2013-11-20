# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
Create a new document with defaults set
"""

import webnotes
from webnotes.utils import nowdate, nowtime, cint, flt
import webnotes.defaults

def get_new_doc(doctype, parent_doc = None, parentfield = None):
	doc = webnotes.doc({
		"doctype": doctype,
		"__islocal": 1,
		"owner": webnotes.session.user,
		"docstatus": 0
	})
	
	meta = webnotes.get_doctype(doctype)
	
	if parent_doc:
		doc.parent = parent_doc.name
		doc.parenttype = parent_doc.doctype
	
	if parentfield:
		doc.parentfield = parentfield
	
	for d in meta.get({"doctype":"DocField", "parent": doctype}):
		default = webnotes.defaults.get_user_default(d.fieldname)
		if default:
			doc.fields[d.fieldname] = default
		elif d.fields.get("default"):
			if d.default == "__user":
				doc.fields[d.fieldname] = webnotes.session.user
			elif d.default == "Today":
				doc.fields[d.fieldname] = nowdate()

			elif d.default.startswith(":"):
				ref_fieldname = d.default[1:].lower().replace(" ", "_")
				if parent_doc:
					ref_docname = parent_doc.fields[ref_fieldname]
				else:
					ref_docname = webnotes.conn.get_default(ref_fieldname)
				doc.fields[d.fieldname] = webnotes.conn.get_value(d.default[1:], 
					ref_docname, d.fieldname)

			else:
				doc.fields[d.fieldname] = d.default
			
			# convert type of default
			if d.fieldtype in ("Int", "Check"):
				doc.fields[d.fieldname] = cint(doc.fields[d.fieldname])
			elif d.fieldtype in ("Float", "Currency"):
				doc.fields[d.fieldname] = flt(doc.fields[d.fieldname])
				
		elif d.fieldtype == "Time":
			doc.fields[d.fieldname] = nowtime()
			
	return doc
