# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, copy, json
from frappe import _, msgprint
from frappe.utils import cint
import frappe.share

rights = ("read", "write", "create", "delete", "submit", "cancel", "amend",
	"print", "email", "report", "import", "export", "set_user_permissions", "share")

def check_admin_or_system_manager(user=None):
	if not user: user = frappe.session.user

	if ("System Manager" not in frappe.get_roles(user)) and (user!="Administrator"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

def has_permission(doctype, ptype="read", doc=None, verbose=False, user=None):
	"""check if user has permission"""
	if not user: user = frappe.session.user

	if frappe.is_table(doctype):
		if verbose: print "Table type, always true"
		return True

	meta = frappe.get_meta(doctype)

	if ptype=="submit" and not cint(meta.is_submittable):
		if verbose: print "Not submittable"
		return False

	if ptype=="import" and not cint(meta.allow_import):
		if verbose: print "Not importable"
		return False

	if user=="Administrator":
		if verbose: print "Administrator"
		return True

	def false_if_not_shared():
		if ptype in ("read", "write", "share", "email", "print"):
			shared = frappe.share.get_shared(doctype, user, 
				["read" if ptype in ("email", "print") else ptype])
			if doc:
				doc_name = doc if isinstance(doc, basestring) else doc.name
				if doc_name in shared:
					if verbose: print "Shared"
					if ptype in ("read", "write", "share") or meta.permissions[0].get(ptype):
						return True
					
			else:
				if verbose: print "Has a shared document"
				return True

		return False

	role_permissions = get_role_permissions(meta, user=user, verbose=verbose)

	if not role_permissions.get(ptype):
		return false_if_not_shared()

	if doc:
		if isinstance(doc, basestring):
			doc = frappe.get_doc(meta.name, doc)

		if role_permissions["apply_user_permissions"].get(ptype):
			if not user_has_permission(doc, verbose=verbose, user=user,
				user_permission_doctypes=role_permissions.get("user_permission_doctypes", {}).get(ptype) or []):
					if verbose: print "No user permission"
					return false_if_not_shared()

		if not has_controller_permissions(doc, ptype, user=user):
			if verbose: print "No controller permission"
			return false_if_not_shared()

	if verbose:
		print "Has Role"
	return True

def get_doc_permissions(doc, verbose=False, user=None):
	if not user: user = frappe.session.user

	if frappe.is_table(doc.doctype):
		return {"read":1, "write":1}

	meta = frappe.get_meta(doc.doctype)

	role_permissions = copy.deepcopy(get_role_permissions(meta, user=user, verbose=verbose))

	if not cint(meta.is_submittable):
		role_permissions["submit"] = 0

	if not cint(meta.allow_import):
		role_permissions["import"] = 0

	if role_permissions.get("apply_user_permissions"):
		# no user permissions, switch off all user-level permissions
		for ptype in role_permissions:
			if role_permissions["apply_user_permissions"].get(ptype) and not user_has_permission(doc, verbose=verbose, user=user,
		user_permission_doctypes=role_permissions.get("user_permission_doctypes", {}).get(ptype) or []):
				role_permissions[ptype] = 0

	# update share permissions
	role_permissions.update(frappe.db.get_value("DocShare",
		{"share_doctype": doc.doctype, "share_name": doc.name, "user": user},
		["read", "write", "share"], as_dict=True) or {})

	return role_permissions

def get_role_permissions(meta, user=None, verbose=False):
	if not user: user = frappe.session.user
	cache_key = (meta.name, user)

	if not frappe.local.role_permissions.get(cache_key):
		perms = frappe._dict({ "apply_user_permissions": {}, "user_permission_doctypes": {} })
		user_roles = frappe.get_roles(user)

		for p in meta.permissions:
			if cint(p.permlevel)==0 and (p.role in user_roles):
				for ptype in rights:
					perms[ptype] = perms.get(ptype, 0) or cint(p.get(ptype))

					if ptype != "set_user_permissions" and p.get(ptype):
						perms["apply_user_permissions"][ptype] = (perms["apply_user_permissions"].get(ptype, 1)
							and p.get("apply_user_permissions"))

				if p.apply_user_permissions:
					if p.user_permission_doctypes:
						# set user_permission_doctypes in perms
						user_permission_doctypes = json.loads(p.user_permission_doctypes)

						if user_permission_doctypes:
							# perms["user_permission_doctypes"][ptype] would be a list of list like [["User", "Blog Post"], ["User"]]
							for ptype in rights:
								if p.get(ptype):
									perms["user_permission_doctypes"].setdefault(ptype, []).append(user_permission_doctypes)
					else:
						user_permission_doctypes = get_linked_doctypes(meta.name)


		for key, value in perms.get("apply_user_permissions").items():
			if not value:
				del perms["apply_user_permissions"][key]

		frappe.local.role_permissions[cache_key] = perms

	return frappe.local.role_permissions[cache_key]

def user_has_permission(doc, verbose=True, user=None, user_permission_doctypes=None):
	from frappe.defaults import get_user_permissions
	user_permissions = get_user_permissions(user)
	user_permission_doctypes = get_user_permission_doctypes(user_permission_doctypes, user_permissions)

	def check_user_permission(d):
		meta = frappe.get_meta(d.get("doctype"))
		end_result = False

		messages = {}

		# check multiple sets of user_permission_doctypes using OR condition
		for doctypes in user_permission_doctypes:
			result = True

			for df in meta.get_fields_to_check_permissions(doctypes):
				if (df.options in user_permissions and d.get(df.fieldname)
					and d.get(df.fieldname) not in user_permissions[df.options]):
					result = False

					if verbose:
						msg = _("Not allowed to access {0} with {1} = {2}").format(df.options, _(df.label), d.get(df.fieldname))
						if d.parentfield:
							msg = "{doctype}, {row} #{idx}, ".format(doctype=_(d.doctype),
								row=_("Row"), idx=d.idx) + msg

						messages[df.fieldname] = msg

			end_result = end_result or result

		if not end_result and messages:
			for fieldname, msg in messages.items():
				msgprint(msg)

		return end_result

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

def get_user_permission_doctypes(user_permission_doctypes, user_permissions):
	"""returns a list of list like [["User", "Blog Post"], ["User"]]"""
	if user_permission_doctypes:
		# select those user permission doctypes for which user permissions exist!
		user_permission_doctypes = [list(set(doctypes).intersection(set(user_permissions.keys())))
			for doctypes in user_permission_doctypes]

	else:
		user_permission_doctypes = [user_permissions.keys()]

	if len(user_permission_doctypes) > 1:
		# OPTIMIZATION
		# if intersection exists, use that to reduce the amount of querying
		# for example, [["Blogger", "Blog Category"], ["Blogger"]], should only search in [["Blogger"]] as the first and condition becomes redundant

		common = user_permission_doctypes[0]
		for i in xrange(1, len(user_permission_doctypes), 1):
			common = list(set(common).intersection(set(user_permission_doctypes[i])))
			if not common:
				break

		if common:
			# is common one of the user_permission_doctypes set?
			for doctypes in user_permission_doctypes:
				# are these lists equal?
				if set(common) == set(doctypes):
					user_permission_doctypes = [common]
					break

	return user_permission_doctypes

def reset_perms(doctype):
	"""Reset permissions for given doctype."""
	from frappe.desk.notifications import delete_notification_count_for
	delete_notification_count_for(doctype)

	frappe.db.sql("""delete from tabDocPerm where parent=%s""", doctype)
	frappe.reload_doc(frappe.db.get_value("DocType", doctype, "module"),
		"DocType", doctype, force=True)

def get_linked_doctypes(dt):
	return list(set([dt] + [d.options for d in
		frappe.get_meta(dt).get("fields", {
			"fieldtype":"Link",
			"ignore_user_permissions":("!=", 1),
			"options": ("!=", "[Select]")
		})
	]))
