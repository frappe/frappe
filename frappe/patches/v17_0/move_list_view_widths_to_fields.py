import json

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model import core_doctypes_list
from frappe.utils import cint


def execute():
	"""Widths in List View Settings applied to everyone. The List Settings width is now each user's own,
	so move these widths to the fields, where admins set the width for everyone: Customize Form for a
	standard DocType, the Custom Field, or the DocType itself for a custom DocType.

	A width already set for the field on this site is kept. Core DocTypes cannot be customized, so
	their widths are dropped, like those of the Status and ID columns, which are not fields.
	"""
	for doctype, fields in frappe.get_all("List View Settings", fields=["name", "fields"], as_list=True):
		columns = json.loads(fields or "[]")
		widths = {}
		for column in columns:
			if width := cint(column.pop("width", 0)):
				widths[column.get("fieldname")] = width

		if not widths:
			continue

		if frappe.db.exists("DocType", doctype) and doctype not in core_doctypes_list:
			set_field_widths(doctype, widths)

		frappe.db.set_value(
			"List View Settings", doctype, "fields", json.dumps(columns), update_modified=False
		)


def set_field_widths(doctype, widths):
	meta = frappe.get_meta(doctype)
	set_in_customize_form = set(
		frappe.get_all("Property Setter", {"doc_type": doctype, "property": "width"}, pluck="field_name")
	)

	for fieldname, width in widths.items():
		df = meta.get_field(fieldname)
		if not df:
			continue

		if meta.custom:
			if not df.width:
				frappe.db.set_value(
					"DocField", {"parent": doctype, "fieldname": fieldname}, "width", str(width)
				)
		elif df.get("is_custom_field"):
			if not df.width:
				frappe.db.set_value(
					"Custom Field", {"dt": doctype, "fieldname": fieldname}, "width", str(width)
				)
		elif fieldname not in set_in_customize_form:
			make_property_setter(doctype, fieldname, "width", str(width), "Data", is_system_generated=False)

	frappe.clear_cache(doctype=doctype)
