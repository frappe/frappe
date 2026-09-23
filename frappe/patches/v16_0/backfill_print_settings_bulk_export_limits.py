import frappe


def execute():
	"""Fill in Print Settings bulk-export limits on sites that predate these fields."""
	frappe.reload_doctype("Print Settings")

	print_settings = frappe.get_single("Print Settings")
	if not print_settings.get("max_bulk_print_docs"):
		print_settings.max_bulk_print_docs = 100
	if not print_settings.get("max_concurrent_bulk_exports"):
		print_settings.max_concurrent_bulk_exports = 5

	print_settings.flags.ignore_mandatory = True
	print_settings.save()
