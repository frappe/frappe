# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import copy

import frappe
import frappe.share
from frappe import _, msgprint
from frappe.query_builder import DocType
from frappe.utils import cint, cstr

rights = (
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"import",
	"export",
	"set_user_permissions",
	"share",
)


def check_admin_or_system_manager(user=None):
	from frappe.utils.commands import warn

	warn(
		"The function check_admin_or_system_manager will be deprecated in version 15."
		'Please use frappe.only_for("System Manager") instead.',
		category=PendingDeprecationWarning,
	)

	if not user:
		user = frappe.session.user

	if ("System Manager" not in frappe.get_roles(user)) and (user != "Administrator"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def print_has_permission_check_logs(func):
	def inner(*args, **kwargs):
		frappe.flags["has_permission_check_logs"] = []
		result = func(*args, **kwargs)
		self_perm_check = True if not kwargs.get("user") else kwargs.get("user") == frappe.session.user
		raise_exception = False if kwargs.get("raise_exception") is False else True

		# print only if access denied
		# and if user is checking his own permission
		if not result and self_perm_check and raise_exception:
			msgprint(("<br>").join(frappe.flags.get("has_permission_check_logs", [])))
		frappe.flags.pop("has_permission_check_logs", None)
		return result

	return inner


@print_has_permission_check_logs
def has_permission(
	doctype,
	ptype="read",
	doc=None,
	verbose=False,
	user=None,
	raise_exception=True,
	*,
	parent_doctype=None,
):
	"""Returns True if user has permission `ptype` for given `doctype`.
	If `doc` is passed, it also checks user, share and owner permissions.

	:param doctype: DocType to check permission for
	:param ptype: Permission Type to check
	:param doc: Check User Permissions for specified document.
	:param verbose: DEPRECATED, will be removed in a future release.
	:param user: User to check permission for. Defaults to current user.
	:param raise_exception:
	        DOES NOT raise an exception.
	        If not False, will display a message using frappe.msgprint
	                which explains why the permission check failed.

	:param parent_doctype:
	        Required when checking permission for a child DocType (unless doc is specified)
	"""

	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	if ptype == "share" and frappe.get_system_settings("disable_document_sharing"):
		return False

	if not doc and hasattr(doctype, "doctype"):
		# first argument can be doc or doctype
		doc = doctype
		doctype = doc.doctype

	if frappe.is_table(doctype):
		return has_child_permission(doctype, ptype, doc, user, raise_exception, parent_doctype)

	meta = frappe.get_meta(doctype)

	if doc:
		if isinstance(doc, str):
			doc = frappe.get_doc(meta.name, doc)
		perm = get_doc_permissions(doc, user=user, ptype=ptype).get(ptype)
		if not perm:
			push_perm_check_log(
				_("User {0} does not have access to this document").format(frappe.bold(user))
			)
	else:
		if ptype == "submit" and not cint(meta.is_submittable):
			push_perm_check_log(_("Document Type is not submittable"))
			return False

		if ptype == "import" and not cint(meta.allow_import):
			push_perm_check_log(_("Document Type is not importable"))
			return False

		role_permissions = get_role_permissions(meta, user=user)
		perm = role_permissions.get(ptype)

		if not perm:
			push_perm_check_log(
				_("User {0} does not have doctype access via role permission for document {1}").format(
					frappe.bold(user), frappe.bold(doctype)
				)
			)

	def false_if_not_shared():
		if ptype in ("read", "write", "share", "submit", "email", "print"):

			rights = ["read" if ptype in ("email", "print") else ptype]

			if doc:
				doc_name = get_doc_name(doc)
				shared = frappe.share.get_shared(
					doctype,
					user,
					rights=rights,
					filters=[["share_name", "=", doc_name]],
					limit=1,
				)

				if shared:
					if ptype in ("read", "write", "share", "submit") or meta.permissions[0].get(ptype):
						return True

			elif frappe.share.get_shared(doctype, user, rights=rights, limit=1):
				# if atleast one shared doc of that type, then return True
				# this is used in db_query to check if permission on DocType
				return True

		return False

	if not perm:
		perm = false_if_not_shared()

	return bool(perm)


def get_doc_permissions(doc, user=None, ptype=None):
	"""Returns a dict of evaluated permissions for given `doc` like `{"read":1, "write":1}`"""
	if not user:
		user = frappe.session.user

	if frappe.is_table(doc.doctype):
		return {"read": 1, "write": 1}

	meta = frappe.get_meta(doc.doctype)

	def is_user_owner():
		return (doc.get("owner") or "").lower() == user.lower()

	if has_controller_permissions(doc, ptype, user=user) is False:
		push_perm_check_log("Not allowed via controller permission check")
		return {ptype: 0}

	permissions = copy.deepcopy(get_role_permissions(meta, user=user, is_owner=is_user_owner()))

	if not cint(meta.is_submittable):
		permissions["submit"] = 0

	if not cint(meta.allow_import):
		permissions["import"] = 0

	# Override with `if_owner` perms irrespective of user
	if permissions.get("has_if_owner_enabled"):
		# apply owner permissions on top of existing permissions
		# some access might be only for the owner
		# eg. everyone might have read access but only owner can delete
		permissions.update(permissions.get("if_owner", {}))

	if not has_user_permission(doc, user):
		if is_user_owner():
			# replace with owner permissions
			permissions = permissions.get("if_owner", {})
			# if_owner does not come with create rights...
			permissions["create"] = 0
		else:
			permissions = {}

	return permissions


def get_role_permissions(doctype_meta, user=None, is_owner=None):
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
	if isinstance(doctype_meta, str):
		doctype_meta = frappe.get_meta(doctype_meta)  # assuming doctype name was passed

	if not user:
		user = frappe.session.user

	cache_key = (doctype_meta.name, user, bool(is_owner))

	if user == "Administrator":
		return allow_everything()

	if not frappe.local.role_permissions.get(cache_key):
		perms = frappe._dict(if_owner={})

		roles = frappe.get_roles(user)

		def is_perm_applicable(perm):
			return perm.role in roles and cint(perm.permlevel) == 0

		def has_permission_without_if_owner_enabled(ptype):
			return any(p.get(ptype, 0) and not p.get("if_owner", 0) for p in applicable_permissions)

		applicable_permissions = list(
			filter(is_perm_applicable, getattr(doctype_meta, "permissions", []))
		)
		has_if_owner_enabled = any(p.get("if_owner", 0) for p in applicable_permissions)
		perms["has_if_owner_enabled"] = has_if_owner_enabled

		for ptype in rights:
			pvalue = any(p.get(ptype, 0) for p in applicable_permissions)
			# check if any perm object allows perm type
			perms[ptype] = cint(pvalue)
			if (
				pvalue
				and has_if_owner_enabled
				and not has_permission_without_if_owner_enabled(ptype)
				and ptype != "create"
			):
				perms["if_owner"][ptype] = cint(pvalue and is_owner)
				# has no access if not owner
				# only provide select or read access so that user is able to at-least access list
				# (and the documents will be filtered based on owner sin further checks)
				perms[ptype] = 1 if ptype in ("select", "read") else 0

		frappe.local.role_permissions[cache_key] = perms

	return frappe.local.role_permissions[cache_key]


def get_user_permissions(user):
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions

	return get_user_permissions(user)


def has_user_permission(doc, user=None):
	"""Returns True if User is allowed to view considering User Permissions"""
	from frappe.core.doctype.user_permission.user_permission import get_user_permissions

	user_permissions = get_user_permissions(user)

	if not user_permissions:
		# no user permission rules specified for this doctype
		return True

	# user can create own role permissions, so nothing applies
	if get_role_permissions("User Permission", user=user).get("write"):
		return True

	apply_strict_user_permissions = frappe.get_system_settings("apply_strict_user_permissions")

	doctype = doc.get("doctype")
	docname = doc.get("name")

	# STEP 1: ---------------------
	# check user permissions on self
	if doctype in user_permissions:
		allowed_docs = get_allowed_docs_for_doctype(user_permissions.get(doctype, []), doctype)

		# if allowed_docs is empty it states that there is no applicable permission under the current doctype

		# only check if allowed_docs is not empty
		if allowed_docs and docname not in allowed_docs:
			# no user permissions for this doc specified
			push_perm_check_log(_("Not allowed for {0}: {1}").format(_(doctype), docname))
			return False

	# STEP 2: ---------------------------------
	# check user permissions in all link fields

	def check_user_permission_on_link_fields(d):
		# check user permissions for all the link fields of the given
		# document object d
		#
		# called for both parent and child records

		meta = frappe.get_meta(d.get("doctype"))

		# check all link fields for user permissions
		for field in meta.get_link_fields():

			if field.ignore_user_permissions:
				continue

			# empty value, do you still want to apply user permissions?
			if not d.get(field.fieldname) and not apply_strict_user_permissions:
				# nah, not strict
				continue

			if field.options not in user_permissions:
				continue

			# get the list of all allowed values for this link
			allowed_docs = get_allowed_docs_for_doctype(user_permissions.get(field.options, []), doctype)

			if allowed_docs and d.get(field.fieldname) not in allowed_docs:
				# restricted for this link field, and no matching values found
				# make the right message and exit
				if d.get("parentfield"):
					# "Not allowed for Company = Restricted Company in Row 3. Restricted field: reference_type"
					msg = _("Not allowed for {0}: {1} in Row {2}. Restricted field: {3}").format(
						_(field.options), d.get(field.fieldname), d.idx, field.fieldname
					)
				else:
					# "Not allowed for Company = Restricted Company. Restricted field: reference_type"
					msg = _("Not allowed for {0}: {1}. Restricted field: {2}").format(
						_(field.options), d.get(field.fieldname), field.fieldname
					)

				push_perm_check_log(msg)

				return False

		return True

	if not check_user_permission_on_link_fields(doc):
		return False

	for d in doc.get_all_children():
		if not check_user_permission_on_link_fields(d):
			return False

	return True


def has_controller_permissions(doc, ptype, user=None):
	"""Returns controller permissions if defined. None if not defined"""
	if not user:
		user = frappe.session.user

	methods = frappe.get_hooks("has_permission").get(doc.doctype, [])

	if not methods:
		return None

	for method in reversed(methods):
		controller_permission = frappe.call(frappe.get_attr(method), doc=doc, ptype=ptype, user=user)
		if controller_permission is not None:
			return controller_permission

	# controller permissions could not decide on True or False
	return None


def get_doctypes_with_read():
	return list({cstr(p.parent) for p in get_valid_perms() if p.parent})


def get_valid_perms(doctype=None, user=None):
	"""Get valid permissions for the current user from DocPerm and Custom DocPerm"""
	roles = get_roles(user)

	perms = get_perms_for(roles)
	custom_perms = get_perms_for(roles, "Custom DocPerm")

	doctypes_with_custom_perms = get_doctypes_with_custom_docperms()
	for p in perms:
		if not p.parent in doctypes_with_custom_perms:
			custom_perms.append(p)

	if doctype:
		return [p for p in custom_perms if p.parent == doctype]
	else:
		return custom_perms


def get_all_perms(role):
	"""Returns valid permissions for a given role"""
	perms = frappe.get_all("DocPerm", fields="*", filters=dict(role=role))
	custom_perms = frappe.get_all("Custom DocPerm", fields="*", filters=dict(role=role))
	doctypes_with_custom_perms = frappe.get_all("Custom DocPerm", pluck="parent", distinct=True)

	for p in perms:
		if p.parent not in doctypes_with_custom_perms:
			custom_perms.append(p)
	return custom_perms


def get_roles(user=None, with_standard=True):
	"""get roles of current user"""
	if not user:
		user = frappe.session.user

	if user == "Guest" or not user:
		return ["Guest"]

	def get():
		if user == "Administrator":
			return frappe.get_all("Role", pluck="name")  # return all available roles
		else:
			table = DocType("Has Role")
			roles = (
				frappe.qb.from_(table)
				.where(
					(table.parenttype == "User") & (table.parent == user) & (table.role.notin(["All", "Guest"]))
				)
				.select(table.role)
				.run(pluck=True)
			)
			return roles + ["All", "Guest"]

	roles = frappe.cache().hget("roles", user, get)

	# filter standard if required
	if not with_standard:
		roles = [r for r in roles if r not in ["All", "Guest", "Administrator"]]

	return roles


def get_doctype_roles(doctype, access_type="read"):
	"""Returns a list of roles that are allowed to access passed doctype."""
	meta = frappe.get_meta(doctype)
	return [d.role for d in meta.get("permissions") if d.get(access_type)]


def get_perms_for(roles, perm_doctype="DocPerm"):
	"""Get perms for given roles"""
	filters = {"permlevel": 0, "docstatus": 0, "role": ["in", roles]}
	return frappe.get_all(perm_doctype, fields=["*"], filters=filters)


def get_doctypes_with_custom_docperms():
	"""Returns all the doctypes with Custom Docperms"""

	doctypes = frappe.get_all("Custom DocPerm", fields=["parent"], distinct=1)
	return [d.parent for d in doctypes]


def can_set_user_permissions(doctype, docname=None):
	# System Manager can always set user permissions
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return True

	meta = frappe.get_meta(doctype)

	# check if current user has read permission for docname
	if docname and not has_permission(doctype, "read", docname):
		return False

	# check if current user has a role that can set permission
	if get_role_permissions(meta).set_user_permissions != 1:
		return False

	return True


def set_user_permission_if_allowed(doctype, name, user, with_message=False):
	if get_role_permissions(frappe.get_meta(doctype), user).set_user_permissions != 1:
		add_user_permission(doctype, name, user)


def add_user_permission(
	doctype,
	name,
	user,
	ignore_permissions=False,
	applicable_for=None,
	is_default=0,
	hide_descendants=0,
):
	"""Add user permission"""
	from frappe.core.doctype.user_permission.user_permission import user_permission_exists

	if not user_permission_exists(user, doctype, name, applicable_for):
		if not frappe.db.exists(doctype, name):
			frappe.throw(_("{0} {1} not found").format(_(doctype), name), frappe.DoesNotExistError)

		frappe.get_doc(
			dict(
				doctype="User Permission",
				user=user,
				allow=doctype,
				for_value=name,
				is_default=is_default,
				applicable_for=applicable_for,
				apply_to_all_doctypes=0 if applicable_for else 1,
				hide_descendants=hide_descendants,
			)
		).insert(ignore_permissions=ignore_permissions)


def remove_user_permission(doctype, name, user):
	user_permission_name = frappe.db.get_value(
		"User Permission", dict(user=user, allow=doctype, for_value=name)
	)
	frappe.delete_doc("User Permission", user_permission_name)


def clear_user_permissions_for_doctype(doctype, user=None):
	filters = {"allow": doctype}
	if user:
		filters["user"] = user
	user_permissions_for_doctype = frappe.get_all("User Permission", filters=filters)
	for d in user_permissions_for_doctype:
		frappe.delete_doc("User Permission", d.name)


def can_import(doctype, raise_exception=False):
	if not ("System Manager" in frappe.get_roles() or has_permission(doctype, "import")):
		if raise_exception:
			raise frappe.PermissionError(f"You are not allowed to import: {doctype}")
		else:
			return False
	return True


def can_export(doctype, raise_exception=False):
	if "System Manager" in frappe.get_roles():
		return True
	else:
		role_permissions = frappe.permissions.get_role_permissions(doctype)
		has_access = role_permissions.get("export") or role_permissions.get("if_owner").get("export")
		if not has_access and raise_exception:
			raise frappe.PermissionError(_("You are not allowed to export {} doctype").format(doctype))
		return has_access


def update_permission_property(
	doctype,
	role,
	permlevel,
	ptype,
	value=None,
	validate=True,
	if_owner=0,
):
	"""Update a property in Custom Perm"""
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

	out = setup_custom_perms(doctype)

	name = frappe.db.get_value(
		"Custom DocPerm", dict(parent=doctype, role=role, permlevel=permlevel, if_owner=if_owner)
	)
	table = DocType("Custom DocPerm")
	frappe.qb.update(table).set(ptype, value).where(table.name == name).run()

	if validate:
		validate_permissions_for_doctype(doctype)

	return out


def setup_custom_perms(parent):
	"""if custom permssions are not setup for the current doctype, set them up"""
	if not frappe.db.exists("Custom DocPerm", dict(parent=parent)):
		copy_perms(parent)
		return True


def add_permission(doctype, role, permlevel=0, ptype=None):
	"""Add a new permission rule to the given doctype
	for the given Role and Permission Level"""
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

	setup_custom_perms(doctype)

	if frappe.db.get_value(
		"Custom DocPerm", dict(parent=doctype, role=role, permlevel=permlevel, if_owner=0)
	):
		frappe.msgprint(
			_("Rule for this doctype, role, permlevel and if-owner combination already exists.").format(
				doctype,
			),
			alert=True,
		)
		return

	if not ptype:
		ptype = "read"

	custom_docperm = frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"__islocal": 1,
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": permlevel,
			ptype: 1,
		}
	)

	custom_docperm.save()

	validate_permissions_for_doctype(doctype)
	return custom_docperm.name


def copy_perms(parent):
	"""Copy all DocPerm in to Custom DocPerm for the given document"""
	for d in frappe.get_all("DocPerm", fields="*", filters=dict(parent=parent)):
		custom_perm = frappe.new_doc("Custom DocPerm")
		custom_perm.update(d)
		custom_perm.insert(ignore_permissions=True)


def reset_perms(doctype):
	"""Reset permissions for given doctype."""
	from frappe.desk.notifications import delete_notification_count_for

	delete_notification_count_for(doctype)
	frappe.db.delete("Custom DocPerm", {"parent": doctype})


def get_linked_doctypes(dt: str) -> list:
	meta = frappe.get_meta(dt)
	linked_doctypes = [dt] + [
		d.options
		for d in meta.get(
			"fields",
			{"fieldtype": "Link", "ignore_user_permissions": ("!=", 1), "options": ("!=", "[Select]")},
		)
	]

	return list(set(linked_doctypes))


def get_doc_name(doc):
	if not doc:
		return None
	return doc if isinstance(doc, str) else str(doc.name)


def allow_everything():
	"""
	returns a dict with access to everything
	eg. {"read": 1, "write": 1, ...}
	"""
	perm = {ptype: 1 for ptype in rights}
	return perm


def get_allowed_docs_for_doctype(user_permissions, doctype):
	"""Returns all the docs from the passed user_permissions that are
	allowed under provided doctype"""
	return filter_allowed_docs_for_doctype(user_permissions, doctype, with_default_doc=False)


def filter_allowed_docs_for_doctype(user_permissions, doctype, with_default_doc=True):
	"""Returns all the docs from the passed user_permissions that are
	allowed under provided doctype along with default doc value if with_default_doc is set"""
	allowed_doc = []
	default_doc = None
	for doc in user_permissions:
		if not doc.get("applicable_for") or doc.get("applicable_for") == doctype:
			allowed_doc.append(doc.get("doc"))
			if doc.get("is_default") or len(user_permissions) == 1 and with_default_doc:
				default_doc = doc.get("doc")

	return (allowed_doc, default_doc) if with_default_doc else allowed_doc


def push_perm_check_log(log):
	if frappe.flags.get("has_permission_check_logs") is None:
		return

	frappe.flags.get("has_permission_check_logs").append(_(log))


def has_child_permission(
	child_doctype,
	ptype="read",
	child_doc=None,
	user=None,
	raise_exception=True,
	parent_doctype=None,
):
	if isinstance(child_doc, str):
		child_doc = frappe.db.get_value(
			child_doctype,
			child_doc,
			("parent", "parenttype", "parentfield"),
			as_dict=True,
		)

	if child_doc:
		parent_doctype = child_doc.parenttype

	if not parent_doctype:
		push_perm_check_log(
			_("Please specify a valid parent DocType for {0}").format(frappe.bold(child_doctype))
		)
		return False

	parent_meta = frappe.get_meta(parent_doctype)

	if parent_meta.istable or not (
		valid_parentfields := [
			df.fieldname for df in parent_meta.get_table_fields() if df.options == child_doctype
		]
	):
		push_perm_check_log(
			_("{0} is not a valid parent DocType for {1}").format(
				frappe.bold(parent_doctype), frappe.bold(child_doctype)
			)
		)
		return False

	if child_doc:
		parentfield = child_doc.parentfield
		if not parentfield:
			push_perm_check_log(
				_("Parentfield not specified in {0}: {1}").format(
					frappe.bold(child_doctype), frappe.bold(child_doc.name)
				)
			)
			return False

		if parentfield not in valid_parentfields:
			push_perm_check_log(
				_("{0} is not a valid parentfield for {1}").format(
					frappe.bold(parentfield), frappe.bold(child_doctype)
				)
			)
			return False

		permlevel = parent_meta.get_field(parentfield).permlevel
		if permlevel > 0 and permlevel not in parent_meta.get_permlevel_access(ptype, user=user):
			push_perm_check_log(
				_("Insufficient Permission Level for {0}").format(frappe.bold(parent_doctype))
			)
			return False

	return has_permission(
		parent_doctype,
		ptype=ptype,
		doc=child_doc and getattr(child_doc, "parent_doc", child_doc.parent),
		user=user,
		raise_exception=raise_exception,
	)
