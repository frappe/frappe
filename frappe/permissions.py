# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint
from frappe.utils import cint
from frappe.defaults import get_restrictions

rights = ("read", "write", "create", "delete", "submit", "cancel", "amend", "print", "email",
	"restricted", "dont_restrict", "can_restrict", "report", "import", "export")

restrictable_rights = ("read", "write", "create", "delete", "submit", "cancel", "amend")

def check_admin_or_system_manager():
	if ("System Manager" not in frappe.get_roles()) and \
	 	(frappe.session.user!="Administrator"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

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

	dont_restrict = (get_user_perms(meta).get("dont_restrict") or ())
	if doc and ptype not in dont_restrict:
		if isinstance(doc, basestring):
			doc = frappe.get_doc(meta.name, doc)

		can_access = apply_restrictions(ptype, doc, verbose=verbose)

		if not can_access:
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

		for p in sorted(meta.permissions, key=lambda p: (p.permlevel, -(p.restricted or 0))):
			if cint(p.permlevel)==0 and (p.role in user_roles):
				for ptype in rights:
					if ptype in ("restricted", "dont_restrict"):
						# list of rights that can be in restricted / don't restrict
						# allows for selectively setting only_restricted on certain rights like submit
						if not perms.get(ptype):
							perms[ptype] = []

						if cint(p.get(ptype)):
							# restricted
							perms[ptype] += [r for r in restrictable_rights if p.get(r)]

						elif ptype == "restricted":
							# not restricted, so remove those rights
							for r in restrictable_rights:
								if p.get(r) and r in perms[ptype]:
									perms[ptype].remove(r)

						# example: perms["restricted"] = ["read", "write", "submit"]
						perms[ptype] = list(set(perms[ptype]))

					else:
						perms[ptype] = perms.get(ptype, 0) or cint(p.get(ptype))

		frappe.local.user_perms[cache_key] = perms

	return frappe.local.user_perms[cache_key]

def apply_restrictions(ptype, doc, verbose=True):
	if doc.owner == frappe.session.user:
		# owner is always allowed
		return True

	restrictions = get_restrictions()
	meta = frappe.get_meta(doc.get("doctype"))

	# handle Only Restricted Documents / Is Creator
	if ptype in (get_user_perms(meta).restricted or ()):
		if not (restrictions and restrictions.get(doc.get("doctype"))):
			# no restrictions specified for this doctype
			return False

		elif doc.name in restrictions.get(doc.get("doctype")):
			# name exists in restrictions for this doctype
			return True

	else:
		if not restrictions:
			return True

	# normal case, check for restrictions in link fields
	can_access_doc = _can_access_doc(doc, restrictions, verbose)
	for d in doc.get_all_children():
		can_access_doc = _can_access_doc(d, restrictions, verbose) and can_access_doc

	# check all restrictions before returning
	return can_access_doc

def _can_access_doc(d, restrictions, verbose):
	# evaluate specific restrictions

	# get link fields to apply restrictions
	meta = frappe.get_meta(d.get("doctype"))
	fields_to_check = meta.get_restricted_fields(restrictions.keys())

	can_access = True
	for df in fields_to_check:
		if d.get(df.fieldname) and d.get(df.fieldname) not in restrictions[df.options]:
			can_access = False

			if verbose:
				msg = _("Not allowed to access {0} with {1} = {2}").format(df.options, _(df.label),
					d.get(df.fieldname))

				if d.parentfield:
					msg = "{doctype}, {row} #{idx}, ".format(doctype=_(d.doctype),
						row=_("Row"), idx=d.idx) + msg

				msgprint(msg)

	return can_access

def has_controller_permissions(doc):
	for method in frappe.get_hooks("has_permission").get(doc.doctype, []):
		if not frappe.call(frappe.get_attr(method), doc=doc):
			return False

	return True

def can_restrict_user(user, doctype, docname=None):
	if not can_restrict(doctype, docname):
		return False

	# check if target user does not have can_restrict permission
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

	# check if current user has a role with can_restrict permission
	if not has_restrict_permission(meta):
		return False

	return True

def has_restrict_permission(meta=None, user=None):
	return True if get_user_perms(meta, user).can_restrict else False

def has_only_non_restrict_role(doctype, user):
	meta = frappe.get_meta(doctype)
	# check if target user does not have can_restrict permission
	if has_restrict_permission(meta, user):
		return False

	# and does not have a role with can_restrict
	return True if not get_user_perms(meta, user).can_restrict else False

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
