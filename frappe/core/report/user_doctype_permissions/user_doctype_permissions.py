# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

from collections import defaultdict

from frappe import _, unscrub
from frappe.permissions import get_valid_perms

PERM_TYPES = [
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
	user = filters.pop("user")
	return get_columns(), get_data(user)


def get_columns() -> list[dict]:
	"""Return a list of columns for this report.

	The first two columns are *DocType* and *Is Owner*. The remaining ones each
	represent a permission type.
	"""
	columns = [
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
		for perm_type in PERM_TYPES
	)

	return columns


def get_data(user: str) -> list[list]:
	"""Return the data for this report.

	This function retrieves the permissions data for a given user. It aggregates
	the permission values by doctype and if_owner flag, and returns the data as
	a list of lists.

	Args:
	        user (str): The user for whom to retrieve the permissions.
	"""
	agg_perms = defaultdict(lambda: {perm_type: 0 for perm_type in PERM_TYPES})

	for perm in get_valid_perms(user=user):
		if perm["permlevel"] != 0:  # ignore permlevel
			continue

		dt = perm["parent"]
		if_owner = perm["if_owner"]
		for perm_type in PERM_TYPES:
			if perm_type not in perm:
				continue
			agg_perms[(dt, if_owner)][perm_type] = agg_perms[(dt, if_owner)][perm_type] or perm[perm_type]

	result = []
	sorted_keys = sorted(agg_perms.keys(), key=lambda x: _(x[0]))
	for dt, if_owner in sorted_keys:
		perm = agg_perms[(dt, if_owner)]
		row = [dt, if_owner]
		row.extend(perm[perm_type] for perm_type in PERM_TYPES)
		result.append(row)

	return result
