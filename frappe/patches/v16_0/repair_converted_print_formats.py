import json

import frappe
from frappe.printing.doctype.print_format.classic_converter import DEFAULT_COLUMN_WIDTH_PCT


def execute():
	"""Repair formats converted by migrate_classic_print_formats before the
	converter fixes: font_size landed as 0 (invisible render) and the serial
	column as 5.33% (too narrow). Touches only those two defects so builder
	edits made since the conversion survive."""
	names = frappe.get_all(
		"Print Format",
		filters={"print_format_builder_beta": 1, "classic_format_data": ("is", "set")},
		pluck="name",
	)
	for name in names:
		values = {}
		font_size, format_data = frappe.db.get_value("Print Format", name, ["font_size", "format_data"])
		if not font_size:
			values["font_size"] = 14
		repaired = widen_serial_columns(format_data)
		if repaired:
			values["format_data"] = repaired
		if values:
			frappe.db.set_value("Print Format", name, values, update_modified=False)


def widen_serial_columns(format_data):
	try:
		layout = json.loads(format_data)
	except (TypeError, ValueError):
		return None
	if not isinstance(layout, dict):
		return None

	changed = False
	zones = [layout.get("header"), layout.get("footer"), *layout.get("sections", [])]
	for zone in zones:
		for column in (zone or {}).get("columns", []):
			for field in column.get("fields", []):
				if widen_serial_column(field.get("table_columns")):
					changed = True
	return json.dumps(layout, indent=1) if changed else None


def widen_serial_column(table_columns):
	if not table_columns:
		return False
	sr = table_columns[0]
	width = sr.get("width")
	if sr.get("fieldname") != "idx" or not width or width >= DEFAULT_COLUMN_WIDTH_PCT:
		return False

	# widen Sr to the default and shrink the other columns by the difference,
	# keeping the total unchanged
	others = sum(col.get("width") or 0 for col in table_columns[1:])
	if others:
		factor = (others - (DEFAULT_COLUMN_WIDTH_PCT - width)) / others
		for col in table_columns[1:]:
			if col.get("width"):
				col["width"] = round(col["width"] * factor, 2)
	sr["width"] = DEFAULT_COLUMN_WIDTH_PCT
	return True
