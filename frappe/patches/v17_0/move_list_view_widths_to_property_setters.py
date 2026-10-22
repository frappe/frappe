import json

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.meta import Meta
from frappe.utils import cint


def execute():
	"""Widths in List View Settings applied to everyone. The List Settings width is now each user's own,
	so move these widths to the fields, where Customize Form sets the width for everyone.

	A width already set for the field on this site, in Customize Form or on the Custom Field, is kept.
	"""
	for doctype, fields in frappe.get_all("List View Settings", fields=["name", "fields"], as_list=True):
		columns = json.loads(fields or "[]")
		widths = {}
		for column in columns:
			if width := cint(column.pop("width", 0)):
				widths[column.get("fieldname")] = width

		if not widths:
			continue

		if frappe.db.exists("DocType", doctype) and doctype not in Meta.special_doctypes:
			set_field_widths(doctype, widths)

		frappe.db.set_value(
			"List View Settings", doctype, "fields", json.dumps(columns), update_modified=False
		)


def set_field_widths(doctype, widths):
	meta = frappe.get_meta(doctype)
	set_on_site = set(
		frappe.get_all("Property Setter", {"doc_type": doctype, "property": "width"}, pluck="field_name")
	)

	for fieldname, width in widths.items():
		df = meta.get_field(fieldname)
		if not df or fieldname in set_on_site or (df.get("is_custom_field") and df.width):
			continue
		make_property_setter(doctype, fieldname, "width", str(width), "Data", is_system_generated=False)
