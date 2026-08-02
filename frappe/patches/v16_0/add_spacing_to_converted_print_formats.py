import json

import frappe
from frappe.printing.doctype.print_format.classic_converter import CONVERTED_SECTION_GAP_PX


def execute():
	"""Give already-converted formats the section spacing the converter now writes.

	Classic put the gap in its markup, so the conversion never had to store one and
	every converted format prints its sections flush against each other. Only
	sections that still carry no spacing at all are touched, so anything adjusted in
	the builder since the conversion is left alone."""
	names = frappe.get_all(
		"Print Format",
		filters={"print_format_builder_beta": 1, "classic_format_data": ("is", "set")},
		pluck="name",
	)
	for name in names:
		format_data = frappe.db.get_value("Print Format", name, "format_data")
		spaced = add_section_spacing(format_data)
		if spaced:
			frappe.db.set_value("Print Format", name, "format_data", spaced, update_modified=False)


def add_section_spacing(format_data):
	try:
		layout = json.loads(format_data)
	except (TypeError, ValueError):
		return None
	if not isinstance(layout, dict):
		return None

	changed = False
	# the first section sits directly under the header, which already has its own gap
	for section in (layout.get("sections") or [])[1:]:
		if not isinstance(section, dict) or section.get("margin") or section.get("padding"):
			continue
		section["margin"] = {"top": CONVERTED_SECTION_GAP_PX, "right": 0, "bottom": 0, "left": 0}
		changed = True

	return json.dumps(layout, indent=1) if changed else None
