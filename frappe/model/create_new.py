# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
Create a new document with defaults set
"""

import copy
import frappe
import frappe.defaults
from frappe.model import data_fieldtypes
from frappe.utils import nowdate, nowtime, now_datetime
from frappe.core.doctype.user_permission.user_permission import get_user_permissions

def get_new_doc(doctype, parent_doc = None, parentfield = None, as_dict=False):
	if doctype not in frappe.local.new_doc_templates:
		# cache a copy of new doc as it is called
		# frequently for inserts
		frappe.local.new_doc_templates[doctype] = make_new_doc(doctype)

	doc = copy.deepcopy(frappe.local.new_doc_templates[doctype])

	# doc = make_new_doc(doctype)

	set_dynamic_default_values(doc, parent_doc, parentfield)

	if as_dict:
		return doc
	else:
		return frappe.get_doc(doc)

def make_new_doc(doctype):
	doc = frappe.get_doc({
		"doctype": doctype,
		"__islocal": 1,
		"owner": frappe.session.user,
		"docstatus": 0
	})

	set_user_and_static_default_values(doc)

	doc._fix_numeric_types()
	doc = doc.get_valid_dict(sanitize=False)
	doc["doctype"] = doctype
	doc["__islocal"] = 1

	return doc

def set_user_and_static_default_values(doc):
	user_permissions = get_user_permissions()
	defaults = frappe.defaults.get_defaults()

	for df in doc.meta.get("fields"):
		if df.fieldtype in data_fieldtypes:
			user_default_value = get_user_default_value(df, defaults, user_permissions)
			if user_default_value is not None:
				doc.set(df.fieldname, user_default_value)

			else:
				if df.fieldname != doc.meta.title_field:
					static_default_value = get_static_default_value(df, user_permissions)
					if static_default_value is not None:
						doc.set(df.fieldname, static_default_value)

def get_user_default_value(df, defaults, user_permissions):
	# don't set defaults for "User" link field using User Permissions!
	if df.fieldtype == "Link" and df.options != "User":
		# 1 - look in user permissions only for document_type==Setup
		# We don't want to include permissions of transactions to be used for defaults.
		if (frappe.get_meta(df.options).document_type=="Setup"
			and user_permissions_exist(df, user_permissions)
			and len(user_permissions.get(df.options))==1):
			return user_permissions.get(df.options)[0].get("doc")

		# 2 - Look in user defaults
		user_default = defaults.get(df.fieldname)
		is_allowed_user_default = user_default and (not user_permissions_exist(df, user_permissions)
			or (user_default in user_permissions.get(df.options, [])))

		# is this user default also allowed as per user permissions?
		if is_allowed_user_default:
			return user_default

def get_static_default_value(df, user_permissions):
	# 3 - look in default of docfield
	if df.get("default"):
		if df.default == "__user":
			return frappe.session.user

		elif df.default == "Today":
			return nowdate()

		elif not df.default.startswith(":"):
			# a simple default value
			is_allowed_default_value = (not user_permissions_exist(df, user_permissions)
				or (df.default in user_permissions.get(df.options, [])))

			if df.fieldtype!="Link" or df.options=="User" or is_allowed_default_value:
				return df.default

	elif (df.fieldtype == "Select" and df.options and df.options not in ("[Select]", "Loading...")):
		return df.options.split("\n")[0]

def set_dynamic_default_values(doc, parent_doc, parentfield):
	# these values should not be cached
	user_permissions = get_user_permissions()

	for df in frappe.get_meta(doc["doctype"]).get("fields"):
		if df.get("default"):
			if df.default.startswith(":"):
				default_value = get_default_based_on_another_field(df, user_permissions, parent_doc)
				if default_value is not None and not doc.get(df.fieldname):
					doc[df.fieldname] = default_value

			elif df.fieldtype == "Datetime" and df.default.lower() == "now":
				doc[df.fieldname] = now_datetime()

		if df.fieldtype == "Time":
			doc[df.fieldname] = nowtime()

	if parent_doc:
		doc["parent"] = parent_doc.name
		doc["parenttype"] = parent_doc.doctype

	if parentfield:
		doc["parentfield"] = parentfield

def user_permissions_exist(df, user_permissions):
	return (df.fieldtype=="Link"
		and not getattr(df, "ignore_user_permissions", False)
		and df.options in (user_permissions or []))

def get_default_based_on_another_field(df, user_permissions, parent_doc):
	# default value based on another document
	from frappe.permissions import get_allowed_docs_for_doctype

	ref_doctype =  df.default[1:]
	ref_fieldname = ref_doctype.lower().replace(" ", "_")
	reference_name = parent_doc.get(ref_fieldname) if parent_doc else frappe.db.get_default(ref_fieldname)
	default_value = frappe.db.get_value(ref_doctype, reference_name, df.fieldname)
	is_allowed_default_value = (not user_permissions_exist(df, user_permissions) or
		(default_value in get_allowed_docs_for_doctype(user_permissions[df.options], df.parent)))

	# is this allowed as per user permissions
	if is_allowed_default_value:
		return default_value
