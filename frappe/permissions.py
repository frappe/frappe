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
		
def has_permission(doctype, ptype="read", refdoc=None, verbose=True):
	"""check if user has permission"""
	if frappe.db.get_value("DocType", doctype, "istable")==1:
		return True
	
	meta = frappe.get_doctype(doctype)
	
	if ptype=="submit" and not cint(meta[0].is_submittable):
		return False
	
	if ptype=="import" and not cint(meta[0].allow_import):
		return False
	
	if frappe.session.user=="Administrator":
		return True
		
	# get user permissions
	if not get_user_perms(meta).get(ptype):
		return False
		
	if refdoc:
		if isinstance(refdoc, basestring):
			refdoc = frappe.doc(meta[0].name, refdoc)
		
		if not has_unrestricted_access(meta, refdoc, verbose=verbose):
			return False
		
		if not has_additional_permission(refdoc):
			return False

	return True
		
def get_user_perms(meta, user=None):
	cache_key = (meta[0].name, user)
	if not frappe.local.user_perms.get(cache_key):
		perms = frappe._dict()
		user_roles = frappe.get_roles(user)
	
		for p in meta.get({"doctype": "DocPerm"}):
			if cint(p.permlevel)==0 and (p.role=="All" or p.role in user_roles):
				for ptype in rights:
					if ptype == "restricted":
						perms[ptype] = perms.get(ptype, 1) and cint(p.get(ptype))
					else:
						perms[ptype] = perms.get(ptype, 0) or cint(p.get(ptype))
					
		frappe.local.user_perms[cache_key] = perms

	return frappe.local.user_perms[cache_key]
		
def has_unrestricted_access(meta, refdoc, verbose=True):
	from frappe.defaults import get_restrictions
	restrictions = get_restrictions()
		
	if get_user_perms(meta).restricted:
		if refdoc.owner == frappe.session.user:
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
		if refdoc.get(df.fieldname) and refdoc.get(df.fieldname) not in restrictions[df.options]:
			if verbose:
				msg = "{not_allowed}: {doctype} {having} {label} = {value}".format(
					not_allowed=_("Sorry, you are not allowed to access"), doctype=_(df.options),
					having=_("having"), label=_(df.label), value=refdoc.get(df.fieldname))
			
				if refdoc.parentfield:
					msg = "{doctype}, {row} #{idx}, ".format(doctype=_(refdoc.doctype),
						row=_("Row"), idx=refdoc.idx) + msg
			
				msgprint(msg)
			
			has_restricted_data = True
	
	# check all restrictions before returning
	return False if has_restricted_data else True
	
def has_additional_permission(doc):
	condition_methods = frappe.get_hooks("has_permission:" + doc.doctype)
	for method in frappe.get_hooks("has_permission:" + doc.doctype):
		if not frappe.get_attr(method)(doc):
			return False
		
	return True
	
def can_restrict_user(user, doctype, docname=None):
	if not can_restrict(doctype, docname):
		return False
		
	meta = frappe.get_doctype(doctype)
	
	# check if target user does not have restrict permission
	if has_only_non_restrict_role(meta, user):
		return True
	
	return False
	
def can_restrict(doctype, docname=None):
	# System Manager can always restrict
	if "System Manager" in frappe.get_roles():
		return True
	meta = frappe.get_doctype(doctype)
	
	# check if current user has read permission for docname
	if docname and not has_permission(doctype, "read", docname):
		return False

	# check if current user has a role with restrict permission
	if not has_restrict_permission(meta):
		return False
	
	return True
	
def has_restrict_permission(meta=None, user=None):
	return get_user_perms(meta, user).restrict==1
	
def has_only_non_restrict_role(meta, user):
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
	