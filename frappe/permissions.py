# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint
from frappe.utils import cint

rights = ("read", "write", "create", "submit", "cancel", "amend",
	"report", "import", "export", "print", "email", "restrict", "delete", "restricted")

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

	def _has_unrestricted_access(d):
		meta = frappe.get_meta(d.get("doctype"))

		# evaluate specific restrictions
		fields_to_check = meta.get_restricted_fields(restrictions.keys())

		_has_restricted_data = False
		for df in fields_to_check:
			if d.get(df.fieldname) and d.get(df.fieldname) not in restrictions[df.options]:
				if verbose:
					msg = _("Not allowed to access {0} with {1} = {2}").format(df.options, _(df.label), d.get(df.fieldname))

					if d.parentfield:
						msg = "{doctype}, {row} #{idx}, ".format(doctype=_(d.doctype),
							row=_("Row"), idx=d.idx) + msg

					msgprint(msg)

				_has_restricted_data = True

		return _has_restricted_data

	has_restricted_data = _has_unrestricted_access(doc)
	for d in doc.get_all_children():
		has_restricted_data = _has_unrestricted_access(d) or has_restricted_data

	# check all restrictions before returning
	return False if has_restricted_data else True

def has_controller_permissions(doc):
	for method in frappe.get_hooks("has_permission").get(doc.doctype, []):
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
