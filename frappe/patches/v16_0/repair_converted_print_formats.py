import json

import frappe
from frappe.printing.doctype.print_format.classic_converter import (
	CONVERTED_SECTION_GAP_PX,
	DEFAULT_COLUMN_WIDTH_PCT,
	NUMERIC_DEFAULT_FIELDS,
	missing_numeric_defaults,
)


def execute():
	"""Repair formats converted before the converter fixes: numeric fields left at 0,
	narrow serial columns, sections with no spacing. Nothing else is touched."""
	names = frappe.get_all(
		"Print Format",
		filters={"print_format_builder_beta": 1, "classic_format_data": ("is", "set")},
		pluck="name",
	)
	fields = ["format_data", *NUMERIC_DEFAULT_FIELDS]
	for name in names:
		row = frappe.db.get_value("Print Format", name, fields, as_dict=True)
		values = missing_numeric_defaults(row)
		repaired = repair_layout(row.format_data)
		if repaired:
			values["format_data"] = repaired
		if values:
			frappe.db.set_value("Print Format", name, values, update_modified=False)


def repair_layout(format_data):
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
	if add_section_spacing(layout):
		changed = True
	return json.dumps(layout, indent=1) if changed else None


def add_section_spacing(layout):
	"""Classic carried the gap between blocks in its own markup, so the conversion
	never stored one and converted sections print flush against each other. The
	first section sits under the header, which already has its own gap.

	Skipped entirely once any section carries spacing: that means someone has been
	in the builder since the conversion, and sections they left unspaced were left
	that way on purpose."""
	sections = [s for s in (layout.get("sections") or [])[1:] if isinstance(s, dict)]
	if any(s.get("margin") or s.get("padding") for s in sections):
		return False

	for section in sections:
		section["margin"] = {"top": CONVERTED_SECTION_GAP_PX, "right": 0, "bottom": 0, "left": 0}
	return bool(sections)


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
