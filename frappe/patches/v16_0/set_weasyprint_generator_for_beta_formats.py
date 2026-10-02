import frappe


def execute():
	"""Existing builder formats rendered through WeasyPrint; keep them there explicitly
	now that the renderer is a stored choice."""
	frappe.reload_doctype("Print Format")
	for row in frappe.get_all(
		"Print Format",
		filters={"print_format_builder_beta": 1, "custom_format": 0, "raw_printing": 0},
		fields=["name", "pdf_generator"],
	):
		if row.pdf_generator in ("Typst", "WeasyPrint"):
			continue
		frappe.db.set_value("Print Format", row.name, "pdf_generator", "WeasyPrint", update_modified=False)
