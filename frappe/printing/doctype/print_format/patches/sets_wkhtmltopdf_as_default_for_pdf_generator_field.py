import frappe


def execute():
	"""sets "wkhtmltopdf" as default for pdf_generator field"""
	for pf in frappe.get_all("Print Format", pluck="name"):
		frappe.db.set_value("Print Format", pf, "pdf_generator", "wkhtmltopdf", update_modified=False)
