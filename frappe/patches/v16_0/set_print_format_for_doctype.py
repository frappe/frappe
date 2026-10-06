import frappe


def execute():
	frappe.reload_doctype("Print Format")
	for name in frappe.get_all(
		"Print Format", filters={"print_format_for": ["in", ["", None]]}, pluck="name"
	):
		frappe.db.set_value("Print Format", name, "print_format_for", "DocType", update_modified=False)
