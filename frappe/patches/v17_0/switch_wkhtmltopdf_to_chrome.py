import frappe


def execute():
	print_format = frappe.qb.DocType("Print Format")
	(
		frappe.qb.update(print_format)
		.set(print_format.pdf_generator, "chrome")
		.where(print_format.pdf_generator.isnull() | print_format.pdf_generator.isin(["", "wkhtmltopdf"]))
	).run()

	frappe.db.delete("Singles", {"doctype": "Print Settings", "field": "pdf_generator"})
	property_setters = frappe.get_all(
		"Property Setter",
		filters={"doc_type": "Print Settings", "field_name": "pdf_generator"},
		pluck="name",
	) + frappe.get_all(
		"Property Setter",
		filters={
			"doc_type": "Print Format",
			"field_name": "pdf_generator",
			"value": ("like", "%wkhtmltopdf%"),
		},
		pluck="name",
	)
	for name in property_setters:
		frappe.delete_doc("Property Setter", name, ignore_permissions=True)
	frappe.clear_cache(doctype="Print Settings")
