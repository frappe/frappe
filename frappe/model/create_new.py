# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
Create a new document with defaults set
"""

import frappe
from frappe.utils import nowdate, nowtime, cint, flt
import frappe.defaults

def get_new_doc(doctype, parent_doc = None, parentfield = None):
	doc = frappe.get_doc({
		"doctype": doctype,
		"__islocal": 1,
		"owner": frappe.session.user,
		"docstatus": 0
	})

	restrictions = frappe.defaults.get_restrictions()

	if parent_doc:
		doc.parent = parent_doc.name
		doc.parenttype = parent_doc.doctype

	if parentfield:
		doc.parentfield = parentfield

	defaults = frappe.defaults.get_defaults()

	for d in doc.meta.get("fields"):
		default = defaults.get(d.fieldname)

		if (d.fieldtype=="Link") and d.ignore_restrictions != 1 and (d.options in restrictions)\
			and len(restrictions[d.options])==1:
			doc.set(d.fieldname, restrictions[d.options][0])
		elif default:
			doc.set(d.fieldname, default)
		elif d.get("default"):
			if d.default == "__user":
				doc.set(d.fieldname, frappe.session.user)
			elif d.default == "Today":
				doc.set(d.fieldname, nowdate())

			elif d.default.startswith(":"):
				ref_doctype =  d.default[1:]
				ref_fieldname = ref_doctype.lower().replace(" ", "_")
				if parent_doc:
					ref_docname = parent_doc.get(ref_fieldname)
				else:
					ref_docname = frappe.db.get_default(ref_fieldname)
				doc.set(d.fieldname, frappe.db.get_value(ref_doctype, ref_docname, d.fieldname))
			else:
				doc.set(d.fieldname, d.default)

			# convert type of default
			if d.fieldtype in ("Int", "Check"):
				doc.set(d.fieldname, cint(doc.get(d.fieldname)))
			elif d.fieldtype in ("Float", "Currency"):
				doc.set(d.fieldname, flt(doc.get(d.fieldname)))

		elif d.fieldtype == "Time":
			doc.set(d.fieldname, nowtime())

		elif (d.fieldtype == "Select" and d.options and not d.options.startswith("link:")
			and d.options != "[Select]"):
			doc.set(d.fieldname, d.options.split("\n")[0])

	return doc
