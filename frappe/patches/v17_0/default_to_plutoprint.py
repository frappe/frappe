import frappe


def execute():
	print_format = frappe.qb.DocType("Print Format")
	frappe.qb.update(print_format).set(print_format.pdf_generator, "").where(
		print_format.pdf_generator == "chrome"
	).run()
	frappe.db.set_single_value("Print Settings", "pdf_generator", "PlutoPrint")
