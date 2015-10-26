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
	"""Returns True if user has permission `ptype` for given `doctype`.
	If `doc` is passed, it also checks user, share and owner permissions.

	Note: if Table DocType is passed, it always returns True.
	"""
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
						if verbose: print "Is shared"
						return True

			elif shared:
				# if atleast one shared doc of that type, then return True
				# this is used in db_query to check if permission on DocType
				if verbose: print "Has a shared document"
				return True

		if verbose: print "Not Shared"
		return False

	role_permissions = get_role_permissions(meta, user=user, verbose=verbose)

	if not role_permissions.get(ptype):
		return false_if_not_shared()

	perm = True

	if doc:
		if isinstance(doc, basestring):
			doc = frappe.get_doc(meta.name, doc)

		owner_perm = user_perm = controller_perm = None

		if role_permissions["if_owner"].get(ptype) and ptype!="create":
			owner_perm = doc.owner == frappe.session.user
			if verbose: print "Owner permission: {0}".format(owner_perm)

		# check if user permission
		if not owner_perm and role_permissions["apply_user_permissions"].get(ptype):
			user_perm = user_has_permission(doc, verbose=verbose, user=user,
				user_permission_doctypes=role_permissions.get("user_permission_doctypes", {}).get(ptype) or [])

			if verbose: print "User permission: {0}".format(user_perm)

		if not owner_perm and not user_perm:
			controller_perm = has_controller_permissions(doc, ptype, user=user)

			if verbose: print "Controller permission: {0}".format(controller_perm)

		# permission true if any one condition is explicitly True or all permissions are undefined (None)
		perm = any([owner_perm, user_perm, controller_perm]) or \
			all([owner_perm==None, user_perm==None, controller_perm==None])

		if not perm:
			perm = false_if_not_shared()

	if verbose: print "Final Permission: {0}".format(perm)

	return perm

def get_doc_permissions(doc, verbose=False, user=None):
	"""Returns a dict of evaluated permissions for given `doc` like `{"read":1, "write":1}`"""
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

	# apply owner permissions on top of existing permissions
	if doc.owner == frappe.session.user:
		role_permissions.update(role_permissions.if_owner)

	update_share_permissions(role_permissions, doc, user)

	return role_permissions

def update_share_permissions(role_permissions, doc, user):
	"""Updates share permissions on `role_permissions` for given doc, if shared"""
	share_ptypes = ("read", "write", "share")
	permissions_by_share = frappe.db.get_value("DocShare",
		{"share_doctype": doc.doctype, "share_name": doc.name, "user": user},
		share_ptypes, as_dict=True)

	if permissions_by_share:
		for ptype in share_ptypes:
			if permissions_by_share[ptype]:
				role_permissions[ptype] = 1
		
def get_role_permissions(meta, user=None, verbose=False):
	"""Returns dict of evaluated role permissions like `{"read": True, "write":False}`

	If user permissions are applicable, it adds a dict of user permissions like

		{
			// user permissions will apply on these rights
			"apply_user_permissions": {"read": 1, "write": 1},

			// doctypes that will be applicable for each right
			"user_permission_doctypes": {
				"read": [
					// AND between "DocType 1" and "DocType 2"
					["DocType 1", "DocType 2"],

					// OR

					["DocType 3"]

				]
			}

			"if_owner": {"read": 1, "write": 1}
		}
	"""
	if not user: user = frappe.session.user
	cache_key = (meta.name, user)

	if not frappe.local.role_permissions.get(cache_key):
		perms = frappe._dict({ "apply_user_permissions": {}, "user_permission_doctypes": {}, "if_owner": {} })
		user_roles = frappe.get_roles(user)
		dont_match = []
		has_a_role_with_apply_user_permissions = False

		for p in meta.permissions:
			if cint(p.permlevel)==0 and (p.role in user_roles):
				# apply only for level 0

				for ptype in rights:
					# build if_owner dict if applicable for this right
					perms[ptype] = perms.get(ptype, 0) or cint(p.get(ptype))

					if ptype != "set_user_permissions" and p.get(ptype):
						perms["apply_user_permissions"][ptype] = (perms["apply_user_permissions"].get(ptype, 1)
							and p.get("apply_user_permissions"))

					if p.if_owner and p.get(ptype):
						perms["if_owner"][ptype] = 1

					if p.get(ptype) and not p.if_owner and not p.get("apply_user_permissions"):
						dont_match.append(ptype)

				if p.apply_user_permissions:
					has_a_role_with_apply_user_permissions = True

					if p.user_permission_doctypes:
						# set user_permission_doctypes in perms
						user_permission_doctypes = json.loads(p.user_permission_doctypes)
					else:
						user_permission_doctypes = get_linked_doctypes(meta.name)

					if user_permission_doctypes:
						# perms["user_permission_doctypes"][ptype] would be a list of list like [["User", "Blog Post"], ["User"]]
						for ptype in rights:
							if p.get(ptype):
								perms["user_permission_doctypes"].setdefault(ptype, []).append(user_permission_doctypes)

		# if atleast one record having both Apply User Permission and If Owner unchecked is found,
		# don't match for those rights
		for ptype in rights:
			if ptype in dont_match:
				if perms["apply_user_permissions"].get(ptype):
					del perms["apply_user_permissions"][ptype]

				if perms["if_owner"].get(ptype):
					del perms["if_owner"][ptype]

		# if one row has only "Apply User Permissions" checked and another has only "If Owner" checked,
		# set Apply User Permissions as checked
		# i.e. the case when there is a role with apply_user_permissions as 1, but resultant apply_user_permissions is 0
		if has_a_role_with_apply_user_permissions:
			for ptype in rights:
				if perms["if_owner"].get(ptype) and perms["apply_user_permissions"].get(ptype)==0:
					perms["apply_user_permissions"][ptype] = 1

		# delete 0 values
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
				if (d.get(df.fieldname)
					and d.get(df.fieldname) not in user_permissions.get(df.options, [])):
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
	"""Returns controller permissions if defined. None if not defined"""
	if not user: user = frappe.session.user

	methods = frappe.get_hooks("has_permission").get(doc.doctype, [])

	if not methods:
		return None

	for method in methods:
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
	if cint(frappe.db.get_single_value("System Settings", "ignore_user_permissions_if_missing")):
		# select those user permission doctypes for which user permissions exist!
		user_permission_doctypes = [list(set(doctypes).intersection(set(user_permissions.keys())))
			for doctypes in user_permission_doctypes]

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
