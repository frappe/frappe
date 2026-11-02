import frappe


def execute():
	if not frappe.db.has_column("Print Format", "print_designer"):
		return

	frappe.db.set_value(
		"Print Format",
		{"print_designer": 1, "pdf_generator": "PlutoPrint"},
		"pdf_generator",
		"chrome",
		update_modified=False,
	)
