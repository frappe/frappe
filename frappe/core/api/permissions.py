# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public permissions API — manage role permission rules and user permissions.

Endpoints were consolidated from the permission manager page, the User
Permission doctype and the Role doctype; the old dotted paths keep working
via aliases in the original modules.
"""

import json
from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import (
	clear_permissions_cache,
	validate_permissions_for_doctype,
)
from frappe.core.doctype.permission_type.permission_type import get_doctype_ptype_map
from frappe.exceptions import DoesNotExistError
from frappe.modules.import_file import get_file_path, read_doc_from_file
from frappe.permissions import (
	AUTOMATIC_ROLES,
	get_all_perms,
	reset_perms,
	setup_custom_perms,
	update_permission_property,
)
from frappe.public_api import public
from frappe.utils import cint
from frappe.utils.user import get_users_with_role as _get_user_with_role

not_allowed_in_permission_manager = ["DocType", "Patch Log", "Module Def"]

# ---------------------------------------------------------------------------
# Role permission rules (permission manager)
# ---------------------------------------------------------------------------


@public(group="Permissions")
@frappe.whitelist()
def get_roles_and_doctypes() -> dict:
	"""Return the roles and doctypes that can be managed in the permission manager.

	:return: Dict with `doctypes`, `roles` (label/value lists) and the custom
		permission type map.
	"""
	frappe.only_for("System Manager")

	active_domains = frappe.get_active_domains()

	DocType = frappe.qb.DocType("DocType")
	doctype_domain_condition = (DocType.restrict_to_domain.isnull()) | (DocType.restrict_to_domain == "")
	if active_domains:
		doctype_domain_condition = doctype_domain_condition | DocType.restrict_to_domain.isin(active_domains)

	doctypes = (
		frappe.qb.from_(DocType)
		.select(DocType.name)
		.where(
			(DocType.istable == 0)
			& (DocType.name.notin(not_allowed_in_permission_manager))
			& doctype_domain_condition
		)
		.run(as_dict=True)
	)

	restricted_roles = ["Administrator"]
	if frappe.session.user != "Administrator":
		custom_user_type_roles = frappe.get_all("User Type", filters={"is_standard": 0}, fields=["role"])
		restricted_roles.extend(row.role for row in custom_user_type_roles)
		restricted_roles.extend(AUTOMATIC_ROLES)

	Role = frappe.qb.DocType("Role")
	role_domain_condition = (Role.restrict_to_domain.isnull()) | (Role.restrict_to_domain == "")
	if active_domains:
		role_domain_condition = role_domain_condition | Role.restrict_to_domain.isin(active_domains)

	roles = (
		frappe.qb.from_(Role)
		.select(Role.name)
		.where((Role.name.notin(restricted_roles)) & (Role.disabled == 0) & role_domain_condition)
		.run(as_dict=True)
	)

	doctypes_list = [{"label": _(d.get("name")), "value": d.get("name")} for d in doctypes]
	roles_list = [{"label": _(d.get("name")), "value": d.get("name")} for d in roles]

	return {
		"doctypes": sorted(doctypes_list, key=lambda d: d["label"].casefold()),
		"roles": sorted(roles_list, key=lambda d: d["label"].casefold()),
		"doctype_ptype_map": get_doctype_ptype_map(),
	}


@public(group="Permissions")
@frappe.whitelist()
def get_permissions(doctype: str | None = None, role: str | None = None) -> list:
	"""Return the permission rules for a doctype and/or role.

	:param doctype: filter rules by this DocType
	:param role: filter rules by this role
	:return: The permission rules, with linked doctypes and meta flags attached.
	"""
	from frappe.permissions import get_linked_doctypes

	frappe.only_for("System Manager")

	if role:
		out = get_all_perms(role)
		if doctype:
			out = [p for p in out if p.parent == doctype]

	else:
		filters = {"parent": doctype}
		if frappe.session.user != "Administrator":
			custom_roles = frappe.get_all("Role", filters={"is_custom": 1}, pluck="name")
			filters["role"] = ["not in", custom_roles]

		out = frappe.get_all("Custom DocPerm", fields="*", filters=filters, order_by="permlevel")
		if not out:
			out = frappe.get_all("DocPerm", fields="*", filters=filters, order_by="permlevel")

	linked_doctypes = {}
	for d in out:
		if d.parent not in linked_doctypes:
			try:
				linked_doctypes[d.parent] = get_linked_doctypes(d.parent)
			except DoesNotExistError:
				# exclude & continue if linked doctype is not found
				frappe.clear_last_message()
				continue
		d.linked_doctypes = linked_doctypes[d.parent]
		if meta := frappe.get_meta(d.parent):
			d.is_submittable = meta.is_submittable
			d.in_create = meta.in_create

	return out


@public(group="Permissions")
@frappe.whitelist()
def add_permission_rule(parent: str, role: str, permlevel: int) -> None:
	"""Add a new (custom) permission rule for a role on a doctype.

	:param parent: DocType the rule applies to
	:param role: role the rule applies to
	:param permlevel: perm level of the rule
	"""
	from frappe.permissions import add_permission

	frappe.only_for("System Manager")
	add_permission(parent, role, permlevel)


@public(group="Permissions")
@frappe.whitelist()
def update_permission_rule(
	doctype: str,
	role: str,
	permlevel: int,
	ptype: str,
	value: str | int | None = None,
	if_owner: str | int = 0,
) -> str | None:
	"""Update one property of a role permission rule.

	:param doctype: DocType the rule applies to
	:param role: role the rule applies to, e.g. "Website Manager"
	:param permlevel: perm level the rule applies to
	:param ptype: permission type, e.g. "read", "delete"
	:param value: value for the permission type, None indicates False
	:param if_owner: apply the rule only to the document owner
	:return: "refresh" if the permission was updated successfully.
	"""

	def clear_cache():
		frappe.clear_cache(doctype=doctype)

	frappe.only_for("System Manager")

	if ptype == "report" and value == "1" and if_owner == "1":
		frappe.throw(_("Cannot set 'Report' permission if 'Only If Creator' permission is set"))

	out = update_permission_property(doctype, role, permlevel, ptype, value, if_owner=if_owner)

	if ptype == "if_owner" and value == "1" and cint(permlevel) == 0:
		update_permission_property(doctype, role, permlevel, "report", "0", if_owner=value)

	frappe.db.after_commit.add(clear_cache)

	return "refresh" if out else None


@public(group="Permissions")
@frappe.whitelist()
def remove_permission_rule(doctype: str, role: str, permlevel: int, if_owner: str | int = 0) -> None:
	"""Remove a (custom) permission rule.

	:param doctype: DocType the rule applies to
	:param role: role the rule applies to
	:param permlevel: perm level of the rule
	:param if_owner: whether the targeted rule is an owner-only rule
	"""
	frappe.only_for("System Manager")
	setup_custom_perms(doctype)

	custom_docperms = frappe.db.get_values(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": permlevel, "if_owner": if_owner}
	)
	for name in custom_docperms:
		frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)

	if not frappe.get_all("Custom DocPerm", {"parent": doctype}):
		frappe.throw(_("There must be atleast one permission rule."), title=_("Cannot Remove"))

	validate_permissions_for_doctype(doctype, for_remove=True, alert=True)


@public(group="Permissions")
@frappe.whitelist()
def reset_permissions(doctype: str) -> None:
	"""Reset a doctype's permission rules to the standard ones shipped with it.

	:param doctype: DocType to be reset
	"""
	frappe.only_for("System Manager")

	from frappe.core.doctype.permission_log.permission_log import insert_perm_log

	frappe.flags.skip_perm_log_for_doctype = doctype
	try:
		reset_perms(doctype)
		clear_permissions_cache(doctype)

		doc = frappe.new_doc("DocType")
		doc.name = doctype
		standard_perms = frappe.get_all("DocPerm", filters={"parent": doctype}, fields="*")
		insert_perm_log(
			doc,
			for_doctype="DocType",
			for_document=doctype,
			custom_changes={
				"from": {"permissions": "custom"},
				"to": {
					"permissions": "standard",
					"standard_rules": [
						{"role": p.role, "permlevel": p.permlevel, "read": p.read, "write": p.write}
						for p in standard_perms
					],
				},
				"status": "Reset",
			},
		)
	finally:
		frappe.flags.pop("skip_perm_log_for_doctype", None)


@public(group="Permissions")
@frappe.whitelist()
def get_users_with_role(role: str) -> list[str]:
	"""Return the enabled users that have the given role.

	:param role: name of the Role
	:return: The matching user names.
	"""
	frappe.only_for("System Manager")
	return _get_user_with_role(role)


@public(group="Permissions")
@frappe.whitelist()
def get_standard_permissions(doctype: str) -> list:
	"""Return the standard permission rules a doctype ships with.

	:param doctype: name of the DocType
	:return: The standard permission rules.
	"""
	frappe.only_for("System Manager")
	meta = frappe.get_meta(doctype)
	if meta.custom:
		doc = frappe.get_doc("DocType", doctype)
		return [p.as_dict() for p in doc.permissions]
	else:
		# also used to setup permissions via patch
		path = get_file_path(meta.module, "DocType", doctype)
		return read_doc_from_file(path).get("permissions")


@public(group="Permissions")
@frappe.whitelist()
def get_permission_logs(doctype: str | None = None, limit: int = 20) -> list:
	"""Return recent Permission Log entries for the given DocType (or all if not specified).

	:param doctype: filter logs to a specific DocType; all DocTypes if omitted
	:param limit: maximum number of log entries to return
	:return: The log entries, newest first, with parsed changes.
	"""
	frappe.only_for("System Manager")

	filters = {"for_doctype": "DocType"}
	if doctype:
		filters["for_document"] = doctype

	logs = frappe.get_all(
		"Permission Log",
		filters=filters,
		fields=["name", "changed_by", "creation", "status", "for_document", "changes"],
		order_by="creation desc",
		limit=limit,
	)

	for log in logs:
		log["changed_at"] = log.pop("creation")
		try:
			log["changes"] = frappe.parse_json(log["changes"])
		except Exception:
			pass

	return logs


@public(group="Permissions")
@frappe.whitelist()
def get_user_permissions(user: str | None = None) -> dict:
	"""Get all user permissions of a user as a dict keyed by doctype.

	:param user: the user; when called over HTTP, always the session user
	:return: Dict mapping each restricted doctype to its allowed documents.
	"""
	# When called from the client side, a user can access only their own user
	# permissions, whichever of the endpoint's cmd paths was used.
	if frappe.request and frappe.local.form_dict.cmd in (
		"get_user_permissions",
		"frappe.core.doctype.user_permission.user_permission.get_user_permissions",
		"frappe.core.api.permissions.get_user_permissions",
	):
		user = frappe.session.user

	if not user:
		user = frappe.session.user

	if not user or user in ("Administrator", "Guest"):
		return {}

	cached_user_permissions = frappe.cache.hget("user_permissions", user)

	if cached_user_permissions is not None:
		return cached_user_permissions

	out = {}

	def add_doc_to_perm(perm, doc_name, is_default, hide_descendants):
		# group rules for each type
		# for example if allow is "Customer", then build all allowed customers
		# in a list
		if not out.get(perm.allow):
			out[perm.allow] = []

		out[perm.allow].append(
			frappe._dict(
				{
					"doc": doc_name,
					"applicable_for": perm.get("applicable_for"),
					"is_default": is_default,
					"hide_descendants": hide_descendants,
				}
			)
		)

	try:
		for perm in frappe.get_all(
			"User Permission",
			fields=["allow", "for_value", "applicable_for", "is_default", "hide_descendants"],
			filters=dict(user=user),
		):
			meta = frappe.get_meta(perm.allow)
			add_doc_to_perm(perm, perm.for_value, perm.is_default, perm.hide_descendants)

			if meta.is_nested_set() and not perm.hide_descendants:
				decendants = frappe.db.get_descendants(perm.allow, perm.for_value)
				for doc in decendants:
					add_doc_to_perm(perm, doc, False, False)

		out = frappe._dict(out)
		frappe.cache.hset("user_permissions", user, out)
	except frappe.db.SQLError as e:
		if frappe.db.is_table_missing(e):
			# called from patch
			pass

	return out


@public(group="Permissions")
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_applicable_for_doctype_list(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict[str, Any]
) -> list:
	"""Search doctypes a user permission on the given doctype can be applied to.

	:param doctype: search doctype (unused, standard link search signature)
	:param txt: search text
	:param searchfield: standard link search signature field
	:param start: standard link search signature field
	:param page_len: standard link search signature field
	:param filters: must contain `doctype` — the doctype the user permission restricts
	:return: The matching doctype names.
	"""
	from frappe.desk.form.linked_with import get_linked_doctypes

	actual_doctype = filters.get("doctype")
	linked_doctypes_map = get_linked_doctypes(actual_doctype, True)

	linked_doctypes = []
	for linked_doctype, linked_doctype_values in linked_doctypes_map.items():
		linked_doctypes.append(linked_doctype)
		child_doctype = linked_doctype_values.get("child_doctype")
		if child_doctype:
			linked_doctypes.append(child_doctype)

	linked_doctypes += [actual_doctype]

	if txt:
		linked_doctypes = [d for d in linked_doctypes if txt.lower() in d.lower()]

	linked_doctypes.sort()

	return [[doctype] for doctype in linked_doctypes[start:page_len]]


@public(group="Permissions")
@frappe.whitelist()
def check_applicable_doc_perm(user: str, doctype: str, docname: str | int) -> list:
	"""Return the doctypes a user permission is currently applied to.

	:param user: user the permission belongs to
	:param doctype: doctype the permission restricts
	:param docname: document the permission restricts to
	:return: The applicable doctypes; all linked doctypes if applied to all.
	"""
	from frappe.desk.form.linked_with import get_linked_doctypes

	frappe.only_for("System Manager")
	applicable = []
	doc_exists = frappe.get_all(
		"User Permission",
		fields=["name"],
		filters={
			"user": user,
			"allow": doctype,
			"for_value": docname,
			"apply_to_all_doctypes": 1,
		},
		limit=1,
	)
	if doc_exists:
		applicable = get_linked_doctypes(doctype).keys()
	else:
		data = frappe.get_all(
			"User Permission",
			fields=["applicable_for"],
			filters={
				"user": user,
				"allow": doctype,
				"for_value": docname,
			},
		)
		for permission in data:
			applicable.append(permission.applicable_for)
	return applicable


@public(group="Permissions")
@frappe.whitelist()
def clear_user_permissions(user: str, for_doctype: str) -> int:
	"""Delete all user permissions of a user for one doctype.

	:param user: user the permissions belong to
	:param for_doctype: doctype the permissions restrict
	:return: Number of deleted user permissions.
	"""
	frappe.only_for("System Manager")
	total = frappe.db.count("User Permission", {"user": user, "allow": for_doctype})

	if total:
		frappe.db.delete(
			"User Permission",
			{
				"allow": for_doctype,
				"user": user,
			},
		)
		frappe.clear_cache()

	return total


@public(group="Permissions")
@frappe.whitelist()
def add_user_permissions(data: str | dict[str, Any]) -> int:
	"""Add or update a user permission, optionally per applicable doctype.

	:param data: dict/JSON with user, doctype, docname, apply_to_all_doctypes,
		applicable_doctypes, is_default and hide_descendants
	:return: 1 if permissions were created or updated, 0 otherwise.
	"""
	from frappe.core.doctype.user_permission.user_permission import (
		insert_user_perm,
		remove_applicable,
		remove_apply_to_all,
		update_applicable,
	)

	frappe.only_for("System Manager")
	if isinstance(data, str):
		data = json.loads(data)
	data = frappe._dict(data)

	# get all doctypes on whom this permission is applied
	perm_applied_docs = check_applicable_doc_perm(data.user, data.doctype, data.docname)
	exists = frappe.db.exists(
		"User Permission",
		{
			"user": data.user,
			"allow": data.doctype,
			"for_value": data.docname,
			"apply_to_all_doctypes": 1,
		},
	)
	if data.apply_to_all_doctypes == 1 and not exists:
		remove_applicable(perm_applied_docs, data.user, data.doctype, data.docname)
		insert_user_perm(
			data.user, data.doctype, data.docname, data.is_default, data.hide_descendants, apply_to_all=1
		)
		return 1
	elif len(data.applicable_doctypes) > 0 and data.apply_to_all_doctypes != 1:
		remove_apply_to_all(data.user, data.doctype, data.docname)
		update_applicable(perm_applied_docs, data.applicable_doctypes, data.user, data.doctype, data.docname)
		for applicable in data.applicable_doctypes:
			if applicable not in perm_applied_docs:
				insert_user_perm(
					data.user,
					data.doctype,
					data.docname,
					data.is_default,
					data.hide_descendants,
					applicable=applicable,
				)
			elif exists:
				insert_user_perm(
					data.user,
					data.doctype,
					data.docname,
					data.is_default,
					data.hide_descendants,
					applicable=applicable,
				)
		return 1
	return 0


@public(group="Permissions")
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def role_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: list | dict | str
) -> list:
	"""Search non-custom roles for a link field.

	:param doctype: search doctype (unused, standard link search signature)
	:param txt: search text
	:param searchfield: standard link search signature field
	:param start: standard link search signature field
	:param page_len: standard link search signature field
	:param filters: standard link search signature field
	:return: The matching role names.
	"""
	return frappe.get_all(
		"Role",
		limit_start=start,
		limit_page_length=page_len,
		filters=[
			["Role", "name", "like", f"%{txt}%"],
			["Role", "is_custom", "=", 0],
			["Role", "name", "!=", "All"],
		],
		as_list=True,
	)
