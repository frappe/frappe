# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from datetime import date

import frappe
from frappe import _
from frappe.query_builder import functions
from frappe.query_builder.terms import ValueWrapper


@frappe.whitelist()
def update_event(args: str | dict, field_map: str | dict):
	"""Updates Event (called via calendar) based on passed `field_map`"""
	args = frappe._dict(frappe.parse_json(args))
	field_map = frappe._dict(frappe.parse_json(field_map))
	w = frappe.get_doc(args.doctype, args.name)
	w.set(field_map.start, args[field_map.start])
	w.set(field_map.end, args.get(field_map.end))
	w.save()


def get_event_conditions(doctype, filters=None):
	"""Return SQL conditions with user permissions and filters for event queries."""
	from frappe.desk.reportview import get_filters_cond

	if not frappe.has_permission(doctype):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	return get_filters_cond(doctype, filters, [], with_match_conditions=True)


@frappe.whitelist()
def get_events(
	doctype: str,
	start: date,
	end: date,
	field_map: str | dict,
	filters: str | list | dict | None = None,
	fields: str | list[str] | None = None,
):
	field_map = frappe._dict(frappe.parse_json(field_map))
	fields = frappe.parse_json(fields)

	doc_meta = frappe.get_meta(doctype)
	for d in doc_meta.fields:
		if d.fieldtype == "Color":
			field_map.update({"color": d.fieldname})

	filters = frappe.parse_json(filters) or []

	if not fields:
		fields = [field_map.start, field_map.end, field_map.title, "name"]

	if field_map.color:
		fields.append(field_map.color)

	dt = frappe.qb.DocType(doctype)
	start_field = functions.IfNull(dt[field_map.start], ValueWrapper("0001-01-01 00:00:00"))
	end_field = functions.IfNull(dt[field_map.end], ValueWrapper("2199-12-31 00:00:00"))

	filters += [
		[start_field, "<=", end],
		[end_field, ">=", start],
	]

	fields = list({field for field in fields if field})
	return frappe.get_list(doctype, fields=fields, filters=filters)
