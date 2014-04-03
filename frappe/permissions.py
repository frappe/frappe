# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, _dict
from frappe.utils import cint

rights = ["read", "write", "create", "submit", "cancel", "amend",
	"report", "import", "export", "print", "email", "restrict", "delete", "restricted"]

def check_admin_or_system_manager():
	if ("System Manager" not in frappe.get_roles()) and \
	 	(frappe.session.user!="Administrator"):
		msgprint("Only Allowed for Role System Manager or Administrator", raise_exception=True)
		
def has_permission(doctype, ptype="read", doc=None, verbose=True):
	"""check if user has permission"""
	if frappe.is_table(doctype):
		return True
	
	meta = frappe.get_meta(doctype)
	
	if ptype=="submit" and not cint(meta.is_submittable):
		return False
	
	if ptype=="import" and not cint(meta.allow_import):
		return False
	
	if frappe.session.user=="Administrator":
		return True
		
	# get user permissions
	if not get_user_perms(meta).get(ptype):
		return False
		
	if doc:
		if isinstance(doc, basestring):
			doc = frappe.get_doc(meta.name, doc)
		
		if not has_unrestricted_access(doc, verbose=verbose):
			return False
		
		if not has_controller_permissions(doc):
			return False

	return True
		
def get_user_perms(meta, user=None):
	if not user:
		user = frappe.session.user
	cache_key = (meta.name, user)
	if not frappe.local.user_perms.get(cache_key):
		perms = frappe._dict()
		user_roles = frappe.get_roles(user)
	
		for p in meta.permissions:
			if cint(p.permlevel)==0 and (p.role in user_roles):
				for ptype in rights:
					if ptype == "restricted":
						perms[ptype] = perms.get(ptype, 1) and cint(p.get(ptype))
					else:
						perms[ptype] = perms.get(ptype, 0) or cint(p.get(ptype))
					
		frappe.local.user_perms[cache_key] = perms

	return frappe.local.user_perms[cache_key]
		
def has_unrestricted_access(doc, verbose=True):
	from frappe.defaults import get_restrictions
	restrictions = get_restrictions()
	meta = frappe.get_meta(doc.get("doctype"))

	if get_user_perms(meta).restricted:
		if doc.owner == frappe.session.user:
			# owner is always allowed for restricted permissions
			return True
		elif not restrictions:
			return False
	else:
		if not restrictions:
			return True
	
	# evaluate specific restrictions
	fields_to_check = meta.get_restricted_fields(restrictions.keys())
	
	has_restricted_data = False
	for df in fields_to_check:
		if doc.get(df.fieldname) and doc.get(df.fieldname) not in restrictions[df.options]:
			if verbose:
				msg = "{not_allowed}: {doctype} {having} {label} = {value}".format(
					not_allowed=_("Sorry, you are not allowed to access"), doctype=_(df.options),
					having=_("having"), label=_(df.label), value=doc.get(df.fieldname))
			
				if doc.parentfield:
					msg = "{doctype}, {row} #{idx}, ".format(doctype=_(doc.doctype),
						row=_("Row"), idx=doc.idx) + msg
			
				msgprint(msg)
			
			has_restricted_data = True
	
	# check all restrictions before returning
	return False if has_restricted_data else True
	
def has_controller_permissions(doc):
	if doc.get("__islocal"):
		doc = frappe.get_doc([doc])
	else:
		doc = frappe.get_doc(doc.doctype, doc.name)
	
	condition_methods = frappe.get_hooks("has_permission:" + doc.doctype)
	for method in frappe.get_hooks("has_permission:" + doc.doctype):
		if not frappe.call(frappe.get_attr(method), doc=doc):
			return False
		
	return True
	
def can_restrict_user(user, doctype, docname=None):
	if not can_restrict(doctype, docname):
		return False
		
	# check if target user does not have restrict permission
	if has_only_non_restrict_role(doctype, user):
		return True
	
	return False
	
def can_restrict(doctype, docname=None):
	# System Manager can always restrict
	if "System Manager" in frappe.get_roles():
		return True
	meta = frappe.get_meta(doctype)
	
	# check if current user has read permission for docname
	if docname and not has_permission(doctype, "read", docname):
		return False

	# check if current user has a role with restrict permission
	if not has_restrict_permission(meta):
		return False
	
	return True
	
def has_restrict_permission(meta=None, user=None):
	return get_user_perms(meta, user).restrict==1
	
def has_only_non_restrict_role(doctype, user):
	meta = frappe.get_meta(doctype)
	# check if target user does not have restrict permission
	if has_restrict_permission(meta, user):
		return False
	
	# and has non-restrict role
	return get_user_perms(meta, user).restrict==0

def can_import(doctype, raise_exception=False):
	if not ("System Manager" in frappe.get_roles() or has_permission(doctype, "import")):
		if raise_exception:
			raise frappe.PermissionError("You are not allowed to import: {doctype}".format(doctype=doctype))
		else:
			return False
	return True
	
def can_export(doctype, raise_exception=False):
	if not ("System Manager" in frappe.get_roles() or has_permission(doctype, "export")):
		if raise_exception:
			raise frappe.PermissionError("You are not allowed to export: {doctype}".format(doctype=doctype))
		else:
			return False
	return True
	