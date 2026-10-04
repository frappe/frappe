"""Use native method discovery and permission-filtered DocType metadata."""

import frappe
from frappe import _
from frappe.api import discovery


def discover_site(query, doctype, method):
	if method:
		return discovery.doctype_method(doctype, method) if doctype else discovery.method(method)
	if doctype:
		return doctype_schema(doctype)
	# Users can read a document without permission to list the DocType definition table.
	visible = frappe.get_all("DocType", pluck="name", filters={"istable": 0})
	visible = sorted(name for name in visible if can_read_doctype(name))
	if query:
		response = {"doctypes": [name for name in visible if query.casefold() in name.casefold()][:50]}
		if "System Manager" in frappe.get_roles():
			response["methods"] = discovery.search(query)["results"]
		return response
	return {
		"site": frappe.local.site,
		"user": frappe.session.user,
		"doctypes": visible[:100],
		"total": len(visible),
	}


def doctype_schema(doctype):
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted to read {0}").format(doctype), frappe.PermissionError)
	from frappe.model import get_permitted_fields

	meta = frappe.get_meta(doctype)
	permitted = set(get_permitted_fields(doctype))
	response = {
		"doctype": doctype,
		"module": meta.module,
		"is_single": bool(meta.issingle),
		"is_submittable": bool(meta.is_submittable),
		"fields": [
			{
				"fieldname": field.fieldname,
				"fieldtype": field.fieldtype,
				"label": field.label,
				"options": field.options,
				"reqd": bool(field.reqd),
				"read_only": bool(field.read_only),
			}
			for field in meta.fields
			if field.fieldname in permitted
		],
		"permissions": {
			permission: bool(frappe.has_permission(doctype, permission))
			for permission in ("read", "write", "create", "delete", "submit", "cancel", "amend")
		},
	}
	if "System Manager" in frappe.get_roles():
		response["methods"] = discovery.doctype_methods(doctype)["methods"]
	return response


def can_read_doctype(doctype):
	try:
		return frappe.has_permission(doctype, "read")
	except frappe.PermissionError:
		# A virtual singleton controller can raise while checking its read permission.
		return False
