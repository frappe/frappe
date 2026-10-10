import frappe


def execute():
	print_format = frappe.qb.DocType("Print Format")
	(
		frappe.qb.update(print_format)
		.set(print_format.pdf_generator, "chrome")
		.where(print_format.pdf_generator.isnull() | print_format.pdf_generator.isin(["", "wkhtmltopdf"]))
	).run()

	frappe.db.delete("Singles", {"doctype": "Print Settings", "field": "pdf_generator"})
	frappe.db.delete(
		"Property Setter",
		{
			"doc_type": ("in", ["Print Format", "Print Settings"]),
			"field_name": "pdf_generator",
			"value": ("like", "%wkhtmltopdf%"),
		},
	)
	frappe.clear_cache(doctype="Print Settings")
