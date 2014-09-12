# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
Create a new document with defaults set
"""

import frappe
from frappe.utils import nowdate, nowtime, cint, flt
import frappe.defaults
from frappe.model.db_schema import type_map

def get_new_doc(doctype, parent_doc = None, parentfield = None):
	doc = frappe.get_doc({
		"doctype": doctype,
		"__islocal": 1,
		"owner": frappe.session.user,
		"docstatus": 0
	})

	user_permissions = frappe.defaults.get_user_permissions()

	if parent_doc:
		doc.parent = parent_doc.name
		doc.parenttype = parent_doc.doctype

	if parentfield:
		doc.parentfield = parentfield

	defaults = frappe.defaults.get_defaults()

	for df in doc.meta.get("fields"):
		if df.fieldtype in type_map:
			default_value = get_default_value(df, defaults, user_permissions, parent_doc)
			doc.set(df.fieldname, default_value)

	doc._fix_numeric_types()

	return doc

def get_default_value(df, defaults, user_permissions, parent_doc):
	user_permissions_exist = (df.fieldtype=="Link"
		and not getattr(df, "ignore_user_permissions", False)
		and df.options in (user_permissions or []))

	# don't set defaults for "User" link field using User Permissions!
	if df.fieldtype == "Link" and df.options != "User":
		# 1 - look in user permissions
		if user_permissions_exist and len(user_permissions[df.options])==1:
			return user_permissions[df.options][0]

		# 2 - Look in user defaults
		user_default = defaults.get(df.fieldname)
		is_allowed_user_default = user_default and (not user_permissions_exist
			or (user_default in user_permissions.get(df.options, [])))

		# is this user default also allowed as per user permissions?
		if is_allowed_user_default:
			return user_default

	# 3 - look in default of docfield
	if df.get("default"):
		if df.default == "__user":
			return frappe.session.user

		elif df.default == "Today":
			return nowdate()

		elif df.default.startswith(":"):
			# default value based on another document
			ref_doctype =  df.default[1:]
			ref_fieldname = ref_doctype.lower().replace(" ", "_")
			ref_docname = parent_doc.get(ref_fieldname) if parent_doc else frappe.db.get_default(ref_fieldname)

			default_value = frappe.db.get_value(ref_doctype, ref_docname, df.fieldname)
			is_allowed_default_value = (not user_permissions_exist or
				(default_value in user_permissions.get(df.options, [])))

			# is this allowed as per user permissions
			if is_allowed_default_value:
				return default_value

		# a static default value
		is_allowed_default_value = (not user_permissions_exist or (df.default in user_permissions.get(df.options, [])))
		if df.fieldtype!="Link" or df.options=="User" or is_allowed_default_value:
			return df.default

	elif df.fieldtype == "Time":
		return nowtime()

	elif (df.fieldtype == "Select" and df.options and df.options not in ("[Select]", "Loading...")):
		return df.options.split("\n")[0]
