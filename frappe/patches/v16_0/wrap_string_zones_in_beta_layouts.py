import json

import frappe


def execute():
	"""Builder layouts used to store header and footer as HTML strings; wrap those in
	the zone shape the builder and renderer read now. Standard formats re-sync from
	their app and are left alone."""
	from frappe.utils.print_format_generator import zone_from_html

	frappe.reload_doctype("Print Format")
	for row in frappe.get_all(
		"Print Format",
		filters={"print_format_builder_beta": 1, "standard": "No", "format_data": ("is", "set")},
		fields=["name", "format_data"],
	):
		try:
			layout = json.loads(row.format_data)
		except ValueError:
			continue
		if not isinstance(layout, dict):
			continue
		changed = False
		for zone in ("header", "footer"):
			if isinstance(layout.get(zone), str):
				layout[zone] = zone_from_html(layout[zone])
				changed = True
		if changed:
			frappe.db.set_value(
				"Print Format", row.name, "format_data", json.dumps(layout, indent=1), update_modified=False
			)
