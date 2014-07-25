# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, copy
from frappe import _, msgprint
from frappe.utils import cint

rights = ("read", "write", "create", "delete", "submit", "cancel", "amend",
	"print", "email", "report", "import", "export", "set_user_permissions")

def check_admin_or_system_manager(user=None):
	if not user: user = frappe.session.user

	if ("System Manager" not in frappe.get_roles(user)) and (user!="Administrator"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

def has_permission(doctype, ptype="read", doc=None, verbose=True, user=None):
	"""check if user has permission"""
	if not user: user = frappe.session.user

	if frappe.is_table(doctype):
		return True

	meta = frappe.get_meta(doctype)

	if ptype=="submit" and not cint(meta.is_submittable):
		return False

	if ptype=="import" and not cint(meta.allow_import):
		return False

	if user=="Administrator":
		return True

	role_permissions = get_role_permissions(meta, user=user)
	if not role_permissions.get(ptype):
		return False

	if doc:
		if isinstance(doc, basestring):
			doc = frappe.get_doc(meta.name, doc)

		if role_permissions["apply_user_permissions"].get(ptype):
			if not user_has_permission(doc, verbose=verbose, user=user):
				return False

		if not has_controller_permissions(doc, ptype, user=user):
			return False

	return True

def get_doc_permissions(doc, verbose=False, user=None):
	if not user: user = frappe.session.user

	if frappe.is_table(doc.doctype):
		return {"read":1, "write":1}

	meta = frappe.get_meta(doc.doctype)

	role_permissions = copy.deepcopy(get_role_permissions(meta, user=user))

	if not cint(meta.is_submittable):
		role_permissions["submit"] = 0

	if not cint(meta.allow_import):
		role_permissions["import"] = 0

	if not user_has_permission(doc, verbose=verbose, user=user):
		# no user permissions, switch off all user-level permissions
		for ptype in role_permissions:
			if role_permissions["apply_user_permissions"].get(ptype):
				role_permissions[ptype] = 0

	return role_permissions

def get_role_permissions(meta, user=None):
	if not user: user = frappe.session.user
	cache_key = (meta.name, user)

	if not frappe.local.role_permissions.get(cache_key):
		perms = frappe._dict({ "apply_user_permissions": {} })
		user_roles = frappe.get_roles(user)

		for p in meta.permissions:
			if cint(p.permlevel)==0 and (p.role in user_roles):
				for ptype in rights:
					perms[ptype] = perms.get(ptype, 0) or cint(p.get(ptype))

					if ptype != "set_user_permissions" and p.get(ptype):
						perms["apply_user_permissions"][ptype] = perms["apply_user_permissions"].get(ptype, 1) and p.get("apply_user_permissions")

		for key, value in perms.get("apply_user_permissions").items():
			if not value:
				del perms["apply_user_permissions"][key]

		frappe.local.role_permissions[cache_key] = perms

	return frappe.local.role_permissions[cache_key]

def user_has_permission(doc, verbose=True, user=None):
	from frappe.defaults import get_user_permissions
	user_permissions = get_user_permissions(user)
	user_permissions_keys = user_permissions.keys()

	def check_user_permission(d):
		result = True
		meta = frappe.get_meta(d.get("doctype"))
		for df in meta.get_fields_to_check_permissions(user_permissions_keys):
			if d.get(df.fieldname) and d.get(df.fieldname) not in user_permissions[df.options]:
				result = False

				if verbose:
					msg = _("Not allowed to access {0} with {1} = {2}").format(df.options, _(df.label), d.get(df.fieldname))
					if d.parentfield:
						msg = "{doctype}, {row} #{idx}, ".format(doctype=_(d.doctype),
							row=_("Row"), idx=d.idx) + msg

					msgprint(msg)

		return result

	_user_has_permission = check_user_permission(doc)
	for d in doc.get_all_children():
		_user_has_permission = check_user_permission(d) and _user_has_permission

	return _user_has_permission

def has_controller_permissions(doc, ptype, user=None):
	if not user: user = frappe.session.user

	for method in frappe.get_hooks("has_permission").get(doc.doctype, []):
		if not frappe.call(frappe.get_attr(method), doc=doc, ptype=ptype, user=user):
			return False

	return True

def can_set_user_permissions(doctype, docname=None):
	# System Manager can always set user permissions
	if "System Manager" in frappe.get_roles():
		return True

	meta = frappe.get_meta(doctype)

	# check if current user has read permission for docname
	if docname and not has_permission(doctype, "read", docname):
		return False

	# check if current user has a role that can set permission
	if get_role_permissions(meta).set_user_permissions!=1:
		return False

	return True

def set_user_permission_if_allowed(doctype, name, user, with_message=False):
	if get_role_permissions(frappe.get_meta(doctype), user).set_user_permissions!=1:
		add_user_permission(doctype, name, user, with_message)

def add_user_permission(doctype, name, user, with_message=False):
	if name not in frappe.defaults.get_user_permissions(user).get(doctype, []):
		if not frappe.db.exists(doctype, name):
			frappe.throw(_("{0} {1} not found").format(_(doctype), name), frappe.DoesNotExistError)

		frappe.defaults.add_default(doctype, name, user, "User Permission")
	elif with_message:
		msgprint(_("Permission already set"))

def remove_user_permission(doctype, name, user, default_value_name=None):
	frappe.defaults.clear_default(key=doctype, value=name, parent=user, parenttype="User Permission",
		name=default_value_name)

def clear_user_permissions_for_doctype(doctype):
	frappe.defaults.clear_default(parenttype="User Permission", key=doctype)

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

def apply_user_permissions(doctype, ptype, user=None):
	"""Check if apply_user_permissions is checked for a doctype, perm type, user combination"""
	role_permissions = get_role_permissions(frappe.get_meta(doctype), user=user)
	return role_permissions.get("apply_user_permissions", {}).get(ptype)
