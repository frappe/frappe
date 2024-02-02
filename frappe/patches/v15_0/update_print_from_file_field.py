import frappe


def execute():
	print_formats = frappe.get_all(
		"Print Format",
		filters={"Standard": "Yes"},
		fields=["name", "print_from_file", "print_format_builder", "print_format_builder_beta"],
	)
	for pf in print_formats:
		if not (pf.print_format_builder or pf.print_format_builder_beta):
			frappe.db.set_value("Print Format", pf.name, "print_from_file", 1)
