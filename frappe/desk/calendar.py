# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from datetime import date

import frappe
from frappe import _
from frappe.query_builder import functions
<<<<<<< HEAD
from frappe.query_builder.terms import ValueWrapper
=======
from frappe.utils import get_datetime, getdate
>>>>>>> 37c13e3 (fix: load calendar events when the user timezone differs from the system)


@frappe.whitelist()
def update_event(args: str, field_map: str):
	"""Updates Event (called via calendar) based on passed `field_map`"""
	args = frappe._dict(json.loads(args))
	field_map = frappe._dict(json.loads(field_map))
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
<<<<<<< HEAD
	start: date,
	end: date,
	field_map: str,
	filters: str | None = None,
=======
	start: str | date,
	end: str | date,
	field_map: str | dict,
	filters: str | list | dict | None = None,
>>>>>>> 37c13e3 (fix: load calendar events when the user timezone differs from the system)
	fields: str | list[str] | None = None,
):
<<<<<<< HEAD
	field_map = frappe._dict(json.loads(field_map))
=======
	start, end = getdate(start), get_datetime(end)

	field_map = frappe._dict(frappe.parse_json(field_map))
>>>>>>> 37c13e3 (fix: load calendar events when the user timezone differs from the system)
	fields = frappe.parse_json(fields)

	doc_meta = frappe.get_meta(doctype)
	for d in doc_meta.fields:
		if d.fieldtype == "Color":
			field_map.update({"color": d.fieldname})

	filters = json.loads(filters) if filters else []

	if not fields:
		fields = [field_map.start, field_map.end, field_map.title, "name"]

	if field_map.color:
		fields.append(field_map.color)

	valid_columns = doc_meta.get_valid_columns()
	for key in ("start", "end"):
		if field_map.get(key) not in valid_columns:
			frappe.throw(_("{0} is not a valid field of {1}").format(field_map.get(key), doctype))

	dt = frappe.qb.DocType(doctype)
	start_field = functions.IfNull(dt[field_map.start], ValueWrapper("0001-01-01 00:00:00"))
	end_field = functions.IfNull(dt[field_map.end], ValueWrapper("2199-12-31 00:00:00"))

	filters += [
		[start_field, "<=", end],
		[end_field, ">=", start],
	]

	fields = list({field for field in fields if field})
	return frappe.get_list(doctype, fields=fields, filters=filters)
