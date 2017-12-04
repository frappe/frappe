# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
from six.moves import range
from six import string_types
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
		if not owner_perm and role_permissions["apply_user_permissions"].get(ptype):
			user_perm = user_has_permission(doc, verbose=verbose, user=user,
				user_permission_doctypes=role_permissions.get("user_permission_doctypes", {}).get(ptype) or [])

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

def user_has_permission(doc, verbose=True, user=None, user_permission_doctypes=None):
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	user_permissions = get_user_permissions(user)
	user_permission_doctypes = get_user_permission_doctypes(user_permission_doctypes, user_permissions)

	def check_user_permission(d):
		meta = frappe.get_meta(d.get("doctype"))
		end_result = False

		messages = {}

		if not user_permission_doctypes:
			# no doctypes restricted
			end_result = True

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

def apply_user_permissions(doctype, ptype, user=None):
	"""Check if apply_user_permissions is checked for a doctype, perm type, user combination"""
	role_permissions = get_role_permissions(frappe.get_meta(doctype), user=user)
	return role_permissions.get("apply_user_permissions", {}).get(ptype)

def get_user_permission_doctypes(user_permission_doctypes, user_permissions):
	"""returns a list of list like [["User", "Blog Post"], ["User"]]"""
	if cint(frappe.get_system_settings('ignore_user_permissions_if_missing')):
		# select those user permission doctypes for which user permissions exist!
		user_permission_doctypes = [
			list(set(doctypes).intersection(set(user_permissions.keys())))
			for doctypes in user_permission_doctypes]

	if len(user_permission_doctypes) > 1:
		# OPTIMIZATION
		# if intersection exists, use that to reduce the amount of querying
		# for example, [["Blogger", "Blog Category"], ["Blogger"]], should only search in [["Blogger"]] as the first and condition becomes redundant

		common = user_permission_doctypes[0]
		for i in range(1, len(user_permission_doctypes), 1):
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

