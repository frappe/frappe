# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
from six import string_types
import frappe, copy, json
from frappe import _, msgprint
from frappe.utils import cint
import frappe.share
rights = ("read", "write", "create", "delete", "submit", "cancel", "amend",
	"print", "email", "report", "import", "export", "set_user_permissions", "share")

# TODO:
# apply_user_permissions
# get_user_permission_doctypes

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

	if verbose:
		print('--- Checking for {0} {1} ---'.format(doctype, doc.name if doc else '-'))

	if frappe.is_table(doctype):
		if verbose: print("Table type, always true")
		return True

	meta = frappe.get_meta(doctype)

	if ptype=="submit" and not cint(meta.is_submittable):
		if verbose: print("Not submittable")
		return False

	if ptype=="import" and not cint(meta.allow_import):
		if verbose: print("Not importable")
		return False

	if user=="Administrator":
		if verbose: print("Allowing Administrator")
		return True

	def false_if_not_shared():
		if ptype in ("read", "write", "share", "email", "print"):
			shared = frappe.share.get_shared(doctype, user,
				["read" if ptype in ("email", "print") else ptype])

			if doc:
				doc_name = doc if isinstance(doc, string_types) else doc.name
				if doc_name in shared:
					if verbose: print("Shared")
					if ptype in ("read", "write", "share") or meta.permissions[0].get(ptype):
						if verbose: print("Is shared")
						return True

			elif shared:
				# if atleast one shared doc of that type, then return True
				# this is used in db_query to check if permission on DocType
				if verbose: print("Has a shared document")
				return True

		if verbose: print("Not Shared")
		return False

	role_permissions = get_role_permissions(meta, user=user, verbose=verbose)

	if not role_permissions.get(ptype):
		return false_if_not_shared()

	perm = True

	if doc:
		if isinstance(doc, string_types):
			doc = frappe.get_doc(meta.name, doc)

		owner_perm = user_perm = controller_perm = None

		if role_permissions["if_owner"].get(ptype) and ptype!="create":
			owner_perm = doc.owner == frappe.session.user
			if verbose: print("Owner permission: {0}".format(owner_perm))

		# check if user permission
		if not owner_perm:
			user_perm = has_user_permission(doc, user, verbose)

			if verbose: print("User permission: {0}".format(user_perm))

		if not owner_perm and not user_perm:
			controller_perm = has_controller_permissions(doc, ptype, user=user)

			if verbose: print("Controller permission: {0}".format(controller_perm))

		# permission true if any one condition is explicitly True or all permissions are undefined (None)
		perm = any([owner_perm, user_perm, controller_perm]) or \
			all([owner_perm==None, user_perm==None, controller_perm==None])

		if not perm:
			perm = false_if_not_shared()

	if verbose: print("Final Permission: {0}".format(perm))

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

	if not has_user_permission(doc, user, verbose):
		role_permissions = {}

	# apply owner permissions on top of existing permissions
	if doc.owner == frappe.session.user and role_permissions.get("if_owner"):
		role_permissions.update(role_permissions.get("if_owner"))

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
		perms = frappe._dict(
			apply_user_permissions={},
			user_permission_doctypes={},
			if_owner={}
		)
		roles = frappe.get_roles(user)
		dont_match = []
		has_a_role_with_apply_user_permissions = False

		for p in meta.permissions:
			if cint(p.permlevel)==0 and (p.role in roles):
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
						try:
							user_permission_doctypes = json.loads(p.user_permission_doctypes)
						except ValueError:
							user_permission_doctypes = []
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
		for key, value in list(perms.get("apply_user_permissions").items()):
			if not value:
				del perms["apply_user_permissions"][key]

		frappe.local.role_permissions[cache_key] = perms

	return frappe.local.role_permissions[cache_key]

def get_user_permissions(user):
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	return get_user_permissions(user)

def has_user_permission(doc, user=None, verbose=True):
	'''Returns True if User is allowed to view considering User Permissions'''
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	user_permissions = get_user_permissions(user)

	def check_user_permission(d):
		meta = frappe.get_meta(d.get("doctype"))

		# check all link fields for user permissions
		for field in meta.get_link_fields():
			# if this type is restricted
			if field.ignore_user_permissions:
				continue

			if field.options in user_permissions:
				if not doc.get(field.fieldname) in user_permissions[field.options]:
					if doc.parentfield:
						# "Not allowed for Company = Restricted Company in Row 3"
						msg = _('Not allowed for {0} = {1} in Row {2}').format(_(field.options), doc[field.fieldname], doc.idx)
					else:
						# "Not allowed for Company = Restricted Company"
						msg = _('Not allowed for {0} = {1}').format(_(field.options), doc.get(field.fieldname))

					if verbose: msgprint(msg)
					if frappe.flags.in_test: print(msg)

					return False
		return True

	result = check_user_permission(doc)
	if not result:
		return False

	for d in doc.get_all_children():
		if not check_user_permission(d):
			return False

	return True

def has_controller_permissions(doc, ptype, user=None):
	"""Returns controller permissions if defined. None if not defined"""
	if not user: user = frappe.session.user

	methods = frappe.get_hooks("has_permission").get(doc.doctype, [])

	if not methods:
		return None

	for method in methods:
		controller_permission = frappe.call(frappe.get_attr(method), doc=doc, ptype=ptype, user=user)
		if controller_permission is not None:
			return controller_permission

	# controller permissions could not decide on True or False
	return None

def get_doctypes_with_read():
	return list(set([p.parent for p in get_valid_perms()]))

def get_valid_perms(doctype=None, user=None):
	'''Get valid permissions for the current user from DocPerm and Custom DocPerm'''
	roles = get_roles(user)

	perms = get_perms_for(roles)
	custom_perms = get_perms_for(roles, 'Custom DocPerm')

	doctypes_with_custom_perms = list(set([d.parent for d in custom_perms]))
	for p in perms:
		if not p.parent in doctypes_with_custom_perms:
			custom_perms.append(p)

	if doctype:
		return [p for p in custom_perms if p.parent == doctype]
	else:
		return custom_perms

def get_all_perms(role):
	'''Returns valid permissions for a given role'''
	perms = frappe.get_all('DocPerm', fields='*', filters=dict(role=role))
	custom_perms = frappe.get_all('Custom DocPerm', fields='*', filters=dict(role=role))
	doctypes_with_custom_perms = frappe.db.sql_list("""select distinct parent
		from `tabCustom DocPerm`""")

	for p in perms:
		if p.parent not in doctypes_with_custom_perms:
			custom_perms.append(p)
	return custom_perms

def get_roles(user=None, with_standard=True):
	"""get roles of current user"""
	if not user:
		user = frappe.session.user

	if user=='Guest':
		return ['Guest']

	def get():
		return [r[0] for r in frappe.db.sql("""select role from `tabHas Role`
			where parent=%s and role not in ('All', 'Guest')""", (user,))] + ['All', 'Guest']

	roles = frappe.cache().hget("roles", user, get)

	# filter standard if required
	if not with_standard:
		roles = filter(lambda x: x not in ['All', 'Guest', 'Administrator'], roles)

	return roles

def get_perms_for(roles, perm_doctype='DocPerm'):
	'''Get perms for given roles'''
	return frappe.db.sql("""
		select * from `tab{doctype}` where docstatus=0
		and ifnull(permlevel,0)=0
		and role in ({roles})""".format(doctype = perm_doctype,
			roles=", ".join(["%s"]*len(roles))), tuple(roles), as_dict=1)

def can_set_user_permissions(doctype, docname=None):
	# System Manager can always set user permissions
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
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

def add_user_permission(doctype, name, user, apply=False):
	'''Add user permission'''
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	if name not in get_user_permissions(user).get(doctype, []):
		if not frappe.db.exists(doctype, name):
			frappe.throw(_("{0} {1} not found").format(_(doctype), name), frappe.DoesNotExistError)

		frappe.get_doc(dict(
			doctype='User Permission',
			user=user,
			allow=doctype,
			for_value=name,
			apply_for_all_roles=apply
		)).insert()

def remove_user_permission(doctype, name, user):
	user_permission_name = frappe.db.get_value('User Permission',
		dict(user=user, allow=doctype, for_value=name))
	frappe.delete_doc('User Permission', user_permission_name)

def clear_user_permissions_for_doctype(doctype):
	frappe.cache().delete_value('user_permissions')

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

def update_permission_property(doctype, role, permlevel, ptype, value=None, validate=True):
	'''Update a property in Custom Perm'''
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
	out = setup_custom_perms(doctype)

	name = frappe.get_value('Custom DocPerm', dict(parent=doctype, role=role,
		permlevel=permlevel))

	frappe.db.sql("""
		update `tabCustom DocPerm`
		set `{0}`=%s where name=%s""".format(ptype), (value, name))
	if validate:
		validate_permissions_for_doctype(doctype)

	return out

def setup_custom_perms(parent):
	'''if custom permssions are not setup for the current doctype, set them up'''
	if not frappe.db.exists('Custom DocPerm', dict(parent=parent)):
		copy_perms(parent)
		return True

def add_permission(doctype, role, permlevel=0):
	'''Add a new permission rule to the given doctype
		for the given Role and Permission Level'''
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
	setup_custom_perms(doctype)

	if frappe.db.get_value('Custom DocPerm', dict(parent=doctype, role=role,
		permlevel=permlevel)):
		return

	custom_docperm = frappe.get_doc({
		"doctype":"Custom DocPerm",
		"__islocal": 1,
		"parent": doctype,
		"parenttype": "DocType",
		"parentfield": "permissions",
		"role": role,
		'read': 1,
		"permlevel": permlevel,
	})

	custom_docperm.save()

	validate_permissions_for_doctype(doctype)

def copy_perms(parent):
	'''Copy all DocPerm in to Custom DocPerm for the given document'''
	for d in frappe.get_all('DocPerm', fields='*', filters=dict(parent=parent)):
		custom_perm = frappe.new_doc('Custom DocPerm')
		custom_perm.update(d)
		custom_perm.insert(ignore_permissions=True)

def reset_perms(doctype):
	"""Reset permissions for given doctype."""
	from frappe.desk.notifications import delete_notification_count_for
	delete_notification_count_for(doctype)

	frappe.db.sql("""delete from `tabCustom DocPerm` where parent=%s""", doctype)

def get_linked_doctypes(dt):
	return list(set([dt] + [d.options for d in
		frappe.get_meta(dt).get("fields", {
			"fieldtype":"Link",
			"ignore_user_permissions":("!=", 1),
			"options": ("!=", "[Select]")
		})
	]))

