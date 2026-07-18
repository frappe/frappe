# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public user API — user lookups, roles, timezones and preferences.

Endpoints were consolidated from the User doctype module and
`frappe.client`; the old dotted paths keep working via aliases in the
original modules.
"""

from typing import Any

import frappe
import frappe.permissions
from frappe.public_api import public


@public(group="User")
@frappe.whitelist(allow_guest=True)
def get_time_zone() -> dict[str, str]:
	"""Return the default time zone of the site.

	:return: Dict with a single `time_zone` key.
	"""
	return {"time_zone": frappe.defaults.get_defaults().get("time_zone")}


@public(group="User")
@frappe.whitelist()
def get_timezones() -> dict[str, list[str]]:
	"""Return all valid time zone names.

	:return: Dict with a single `timezones` list.
	"""
	from frappe.core.doctype.user.user import _get_timezones

	return {"timezones": _get_timezones()}


@public(group="User")
@frappe.whitelist()
def get_all_roles() -> list[str]:
	"""Return all assignable roles, filtered by the active domains.

	:return: The role names, sorted.
	"""
	active_domains = frappe.get_active_domains()

	Role = frappe.qb.DocType("Role")

	domain_condition = (Role.restrict_to_domain.isnull()) | (Role.restrict_to_domain == "")
	if active_domains:
		domain_condition = domain_condition | Role.restrict_to_domain.isin(active_domains)

	roles = (
		frappe.qb.from_(Role)
		.select(Role.name)
		.where(
			(Role.name.notin(frappe.permissions.AUTOMATIC_ROLES)) & (Role.disabled == 0) & domain_condition
		)
		.orderby(Role.name)
		.run(as_dict=True)
	)

	return sorted([role.get("name") for role in roles])


@public(group="User")
@frappe.whitelist()
def get_perm_info(role: str) -> list:
	"""Return the permission rules of a role.

	:param role: name of the Role
	:return: The role's permission rules.
	"""
	from frappe.permissions import get_all_perms

	return get_all_perms(role)


@public(group="User")
@frappe.whitelist()
def has_email_account(email: str) -> list:
	"""Check whether an Email Account exists for the given email address.

	:param email: the email address
	:return: The matching Email Account names, empty if none exist.
	"""
	return frappe.get_list("Email Account", filters={"email_id": email})


@public(group="User")
@frappe.whitelist(allow_guest=False)
def get_email_awaiting(user: str) -> list:
	"""Return a user's inbox email accounts that still await a password.

	:param user: the user; reading other users requires read permission on them
	:return: The awaiting email accounts with their email ids.
	"""
	if user != frappe.session.user:
		frappe.has_permission("User", "read", doc=user, throw=True)

	return frappe.get_all(
		"User Email",
		fields=["email_account", "email_id"],
		filters={"awaiting_password": 1, "parent": user, "used_oauth": 0},
	)


@public(group="User")
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def user_query(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict[str, Any]
) -> list:
	"""Search enabled users for a link field.

	:param doctype: search doctype (always User)
	:param txt: search text, matched against name fields
	:param searchfield: standard link search signature field
	:param start: standard link search signature field
	:param page_len: standard link search signature field
	:param filters: additional filters; `ignore_user_type` includes website users
	:return: The matching users as (name, full_name) rows.
	"""
	doctype = "User"

	list_filters = {
		"enabled": 1,
		"docstatus": ["<", 2],
	}

	# Check if we have a search term, and decide the filters depending on the search term
	or_filters = [[searchfield, "like", f"%{txt}%"]]
	if "name" in searchfield:
		or_filters += [[field, "like", f"%{txt}%"] for field in ("first_name", "middle_name", "last_name")]

	if filters:
		if not (filters.get("ignore_user_type") and frappe.session.data.user_type == "System User"):
			list_filters["user_type"] = ["!=", "Website User"]

		filters.pop("ignore_user_type", None)
		list_filters.update(filters)

	return frappe.get_list(
		doctype,
		filters=list_filters,
		fields=["name", "full_name"],
		limit_start=start,
		limit_page_length=page_len,
		order_by="name asc",
		or_filters=or_filters,
		as_list=True,
	)


@public(group="User")
@frappe.whitelist()
def get_module_profile(module_profile: str) -> list:
	"""Return the blocked modules of a Module Profile.

	:param module_profile: name of the Module Profile
	:return: The profile's blocked modules.
	"""
	module_profile = frappe.get_doc("Module Profile", {"module_profile_name": module_profile})
	return module_profile.get("block_modules")


@public(group="User")
@frappe.whitelist()
def switch_theme(theme: str) -> None:
	"""Set the desk theme of the session user.

	:param theme: "Dark", "Light" or "Automatic"
	"""
	if theme in ["Dark", "Light", "Automatic"]:
		frappe.db.set_value("User", frappe.session.user, "desk_theme", theme)
