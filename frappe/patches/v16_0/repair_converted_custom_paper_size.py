import json

import frappe
from frappe.patches.v16_0.repair_converted_print_formats import add_page_size


def execute():
	"""Give converted classic formats with a Custom paper size their width and height."""
	rows = frappe.get_all(
		"Print Format",
		filters={
			"print_format_builder_beta": 1,
			"classic_format_data": ("is", "set"),
			"paper_size": "Custom",
		},
		fields=["name", "format_data", "paper_size", "paper_width", "paper_height"],
	)
	for row in rows:
		try:
			layout = json.loads(row.format_data)
		except (TypeError, ValueError):
			continue
		if isinstance(layout, dict) and add_page_size(
			layout, row.paper_size, row.paper_width, row.paper_height
		):
			frappe.db.set_value(
				"Print Format", row.name, "format_data", json.dumps(layout, indent=1), update_modified=False
			)
