import json

import frappe
from frappe.printing.doctype.print_format.classic_converter import (
	CONVERTED_SECTION_GAP_PX,
	DEFAULT_COLUMN_WIDTH_PCT,
)


def execute():
	"""Repair formats converted by migrate_classic_print_formats before the
	converter fixes: font_size landed as 0 (invisible render), the serial column as
	5.33% (too narrow) and sections with no spacing between them. Touches only those
	defects so builder edits made since the conversion survive.

	Re-runnable: patches.txt carries a dated entry so sites that already ran an
	earlier version of this patch pick up the later fixes."""
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
		repaired = repair_layout(format_data)
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
	first section sits under the header, which already has its own gap."""
	changed = False
	for section in (layout.get("sections") or [])[1:]:
		if not isinstance(section, dict) or section.get("margin") or section.get("padding"):
			continue
		section["margin"] = {"top": CONVERTED_SECTION_GAP_PX, "right": 0, "bottom": 0, "left": 0}
		changed = True
	return changed


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
