# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _, unscrub
from frappe.permissions import (
	AUTOMATIC_ROLES,
	get_valid_perms,
)

PERM_TYPES = [
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
	"share",
	"export",
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.get("user") or filters.get("doctype")):
		frappe.throw(_("Please set at least one filter: User or DocType"))

	return get_columns(), get_data(filters)


def get_columns() -> list[dict]:
	"""Return a list of columns for this report.

	The first two columns are *DocType* and *Is Owner*. The remaining ones each
	represent a permission type.
	"""
	columns = [
		{
			"label": _("User"),
			"fieldname": "user",
			"fieldtype": "Link",
			"options": "User",
			"width": 200,
		},
		{
			"label": _("DocType"),
			"fieldname": "doc_type",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 200,
		},
		{
			"label": _("If Owner"),
			"fieldname": "if_owner",
			"fieldtype": "Check",
		},
	]

	columns.extend(
		{
			"label": _(unscrub(perm_type)),
			"fieldname": perm_type,
			"fieldtype": "Check",
		}
		for perm_type in get_perm_types()
	)

	return columns


def get_data(filters: dict) -> list[list]:
	"""Return the data for this report.

	This function retrieves the permissions data for a given user. It aggregates
	the permission values by doctype and if_owner flag, and returns the data as
	a list of lists.

	Args:
	        filters (dict): Dictionary containing optional 'user' and 'doctype' keys
	"""
	perm_types = get_perm_types()
	agg_perms = defaultdict(lambda: {perm_type: 0 for perm_type in perm_types})
	doctype, user = filters.get("doctype"), filters.get("user")
	role_user_map = get_all_user_roles() if not user else {}

	for perm in get_valid_perms(doctype, user, role_user_map.keys()):
		if perm["permlevel"] != 0:  # ignore permlevel
			continue

		dt = perm["parent"]
		if_owner = perm["if_owner"]
		role = perm["role"]

		users = [user] if user else role_user_map.get(role, [])

		for perm_type in perm_types:
			if perm_type not in perm:
				continue

			for u in users:
				key = (u, dt, if_owner)
				agg_perms[key][perm_type] = agg_perms[key][perm_type] or perm[perm_type]

	result = []
	sorted_keys = sorted(agg_perms.keys(), key=lambda x: (x[0], x[1]))
	for u, dt, if_owner in sorted_keys:
		perm = agg_perms[(u, dt, if_owner)]
		row = [u, dt, if_owner]
		row.extend(perm[perm_type] for perm_type in perm_types)
		result.append(row)

	return result


def get_all_user_roles():
	HAS_ROLE = frappe.qb.DocType("Has Role")

	user_roles = (
		frappe.qb.from_(HAS_ROLE)
		.where(HAS_ROLE.parenttype == "User")
		.where(HAS_ROLE.role.notin(AUTOMATIC_ROLES))
		.select(HAS_ROLE.parent, HAS_ROLE.role)
		.run()
	)

	role_user_map = defaultdict(list)
	for user, role in user_roles:
		role_user_map[role].append(user)

	return role_user_map


def get_perm_types() -> list[str]:
	"""Return PERM_TYPES extended with custom Permission Types."""
	custom_perm_types = frappe.get_all("Permission Type", pluck="perm_type")
	return PERM_TYPES + custom_perm_types
