import frappe


def execute():
	print_format = frappe.qb.DocType("Print Format")
	(
		frappe.qb.update(print_format)
		.set(print_format.pdf_generator, "chrome")
		.where(print_format.pdf_generator.isnull() | print_format.pdf_generator.isin(["", "wkhtmltopdf"]))
	).run()

	for setter in frappe.get_all(
		"Property Setter",
		filters={"doc_type": "Print Format", "field_name": "pdf_generator", "property": "options"},
		fields=["name", "value"],
	):
		options = (setter.value or "").split("\n")
		if "chrome" not in options:
			frappe.db.set_value("Property Setter", setter.name, "value", "\n".join(["chrome", *options]))

	frappe.db.delete("Singles", {"doctype": "Print Settings", "field": "pdf_generator"})
	for name in frappe.get_all(
		"Property Setter",
		filters={"doc_type": "Print Settings", "field_name": "pdf_generator"},
		pluck="name",
	):
		frappe.delete_doc("Property Setter", name, ignore_permissions=True)
	frappe.clear_cache(doctype="Print Settings")
