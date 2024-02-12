# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.utils.user
from frappe.model import data_fieldtypes
from frappe.permissions import rights


def execute(filters=None):
	frappe.only_for("System Manager")

	user, doctype, show_permissions = (
		filters.get("user"),
		filters.get("doctype"),
		filters.get("show_permissions"),
	)

	columns, fields = get_columns_and_fields(doctype)
	data = frappe.get_list(doctype, fields=fields, as_list=True, user=user)

	if show_permissions:
		columns = columns + [frappe.unscrub(right) + ":Check:80" for right in rights]
		data = list(data)
		for i, doc in enumerate(data):
			permission = frappe.permissions.get_doc_permissions(frappe.get_doc(doctype, doc[0]), user)
			data[i] = doc + tuple(permission.get(right) for right in rights)

	return columns, data


def get_columns_and_fields(doctype):
	columns = [f"Name:Link/{doctype}:200"]
	fields = ["name"]
	for df in frappe.get_meta(doctype).fields:
		if df.in_list_view and df.fieldtype in data_fieldtypes:
			fields.append(f"`{df.fieldname}`")
			fieldtype = f"Link/{df.options}" if df.fieldtype == "Link" else df.fieldtype
			columns.append(f"{df.label}:{fieldtype}:{df.width or 100}")

	return columns, fields


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def query_doctypes(doctype, txt, searchfield, start, page_len, filters):
	user = filters.get("user")
	user_perms = frappe.utils.user.UserPermissions(user)
	user_perms.build_permissions()
	can_read = user_perms.can_read  # Does not include child tables
	include_single_doctypes = filters.get("include_single_doctypes")

	single_doctypes = [d[0] for d in frappe.db.get_values("DocType", {"issingle": 1})]

	return [
		[dt]
		for dt in can_read
		if txt.lower().replace("%", "") in frappe._(dt).lower()
		and (include_single_doctypes or dt not in single_doctypes)
	]
