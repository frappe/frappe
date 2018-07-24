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

# optimize: meta.get_link_map (check if the doctype link exists for the given permission type)

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

	if not doc and hasattr(doctype, 'doctype'):
		# first argument can be doc or doctype
		doc = doctype
		doctype = doc.doctype

	if verbose:
		doc_name = get_doc_name(doc) or '_'
		print('--- Checking for {0} {1} ---'.format(doctype, doc_name))

	if frappe.is_table(doctype):
		if verbose: print("Table type, always true")
		return True

	if user=="Administrator":
		if verbose: print("Allowing Administrator")
		return True

	meta = frappe.get_meta(doctype)

	if doc:
		if isinstance(doc, string_types):
			doc = frappe.get_doc(meta.name, doc)

		perm = get_doc_permissions(doc, user=user, ptype=ptype).get(ptype)
	else:
		if ptype=="submit" and not cint(meta.is_submittable):
			if verbose: print("Not submittable")
			return False

		if ptype=="import" and not cint(meta.allow_import):
			if verbose: print("Not importable")
			return False

		role_permissions = get_role_permissions(meta, user=user, verbose=verbose)
		perm = role_permissions.get(ptype)

	def false_if_not_shared():
		if ptype in ("read", "write", "share", "email", "print"):
			shared = frappe.share.get_shared(doctype, user,
				["read" if ptype in ("email", "print") else ptype])

			if doc:
				doc_name = get_doc_name(doc)
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

	if not perm:
		perm = false_if_not_shared()

	if verbose: print("Final Permission: {0}".format(perm))
	return perm

def get_doc_permissions(doc, verbose=False, user=None, ptype=None):
	"""Returns a dict of evaluated permissions for given `doc` like `{"read":1, "write":1}`"""
	if not user: user = frappe.session.user

	if frappe.is_table(doc.doctype): return {"read": 1, "write": 1}

	meta = frappe.get_meta(doc.doctype)

	if has_controller_permissions(doc, ptype, user=user) == False :
		return {ptype: 0}

	permissions = copy.deepcopy(get_role_permissions(meta, user=user, verbose=verbose))

	if not cint(meta.is_submittable):
		permissions["submit"] = 0

	if not cint(meta.allow_import):
		permissions["import"] = 0

	if not has_user_permission(doc, user):
		if not permissions.get("if_owner"): return {}
		# apply owner permissions on top of existing permissions
		if(doc.owner == frappe.session.user):

			permissions = permissions.get("if_owner")
			# if_owner does not come with create rights...
			permissions['create'] = 0
		else:
			permissions = {}

	return permissions

def get_role_permissions(doctype_meta, user=None, verbose=False):
	"""
	Returns dict of evaluated role permissions like
		{
			"read": 1,
			"write": 0,
			// if "if_owner" is enabled
			"if_owner":
				{
					"read": 1,
					"write": 0
				}
		}
	"""
	if isinstance(doctype_meta, string_types):
		doctype_meta = frappe.get_meta(doctype_meta) # assuming doctype name was passed

	if not user: user = frappe.session.user

	cache_key = (doctype_meta.name, user)

	if user == 'Administrator':
		return allow_everything()

	if not frappe.local.role_permissions.get(cache_key):
		perms = frappe._dict(
			if_owner={}
		)

		roles = frappe.get_roles(user)

		def is_perm_applicable(perm):
			return perm.role in roles and cint(perm.permlevel)==0

		def has_permission_without_if_owner_enabled(ptype):
			return any(p.get(ptype, 0) and not p.get('if_owner', 0) for p in applicable_permissions)

		applicable_permissions = list(filter(is_perm_applicable, doctype_meta.permissions))
		has_if_owner_enabled = any(p.get('if_owner', 0) for p in applicable_permissions)

		for ptype in rights:
			pvalue = any(p.get(ptype, 0) for p in applicable_permissions)
			perms[ptype] = cint(pvalue) # check if any perm object allows perm type
			if (pvalue
				and has_if_owner_enabled
				and not has_permission_without_if_owner_enabled(ptype)):
				perms['if_owner'][ptype] = 1

		frappe.local.role_permissions[cache_key] = perms
	return frappe.local.role_permissions[cache_key]

def get_user_permissions(user):
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	return get_user_permissions(user)

def has_user_permission(doc, user=None, verbose=False):
	'''Returns True if User is allowed to view considering User Permissions'''
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	user_permissions = get_user_permissions(user)

	if not user_permissions: return True

	# user can create own role permissions, so nothing applies
	if get_role_permissions('User Permission', user=user).get('write'): return True

	apply_strict_user_permissions = frappe.get_system_settings('apply_strict_user_permissions')

	if doc.get('doctype') in user_permissions:
		if (doc.get('name')
			not in user_permissions[doc.get('doctype')].get("docs", [])
			and not doc.get('doctype') in user_permissions[doc.get('doctype')].get("skip_for_doctype", [])):
			# don't have user permissions on the doc itself!
			if verbose:
				msgprint(_('Not allowed for {0} = {1}').format(_(doc.get('doctype')), doc.get('name')))
			return False

	def check_user_permission(d):
		meta = frappe.get_meta(d.get("doctype"))

		# check all link fields for user permissions
		for field in meta.get_link_fields():
			# if this type is restricted
			if field.ignore_user_permissions: continue

			if (field.options in user_permissions
				and not d.get("doctype") in user_permissions[field.options].get("skip_for_doctype", [])):
				if not apply_strict_user_permissions:
					# ignore if link is not set
					if not d.get(field.fieldname):
						continue

				if not d.get(field.fieldname) in user_permissions.get(field.options, {}).get("docs", []):
					if d.get('parentfield'):
						# "Not allowed for Company = Restricted Company in Row 3"
						msg = _('Not allowed for {0} = {1} in Row {2}').format(_(field.options), d[field.fieldname], d.idx)
					else:
						# "Not allowed for Company = Restricted Company"
						msg = _('Not allowed for {0} = {1}').format(_(field.options), d.get(field.fieldname))

					if verbose: msgprint(msg)

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
		if user == 'Administrator':
			return [r[0] for r in frappe.db.sql("select name from `tabRole`")] # return all available roles
		else:
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
		add_user_permission(doctype, name, user)

def add_user_permission(doctype, name, user, ignore_permissions=False):
	'''Add user permission'''
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions
	if name not in get_user_permissions(user).get(doctype, {}).get('docs', []):
		if not frappe.db.exists(doctype, name):
			frappe.throw(_("{0} {1} not found").format(_(doctype), name), frappe.DoesNotExistError)

		frappe.get_doc(dict(
			doctype='User Permission',
			user=user,
			allow=doctype,
			for_value=name
		)).insert(ignore_permissions=ignore_permissions)

def remove_user_permission(doctype, name, user):
	user_permission_name = frappe.db.get_value('User Permission',
		dict(user=user, allow=doctype, for_value=name))
	frappe.delete_doc('User Permission', user_permission_name)

def clear_user_permissions_for_doctype(doctype, user=None):
	user_permissions_for_doctype = frappe.db.get_list('User Permission',
		dict(user=user, allow=doctype))
	for d in user_permissions_for_doctype:
		frappe.delete_doc('User Permission', d.name)

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

def get_doc_name(doc):
	if not doc: return None
	return doc if isinstance(doc, string_types) else doc.name

def allow_everything():
	'''
	returns a dict with access to everything
	eg. {"read": 1, "write": 1, ...}
	'''
	perm = {ptype: 1 for ptype in rights}
	return perm