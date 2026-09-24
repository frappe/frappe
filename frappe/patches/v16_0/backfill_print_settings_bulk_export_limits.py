import frappe


def execute():
	"""Fill in Print Settings bulk-export limits on sites that predate these fields."""
	frappe.reload_doctype("Print Settings")

	print_settings = frappe.get_single("Print Settings")
	changed = False
	if not print_settings.get("max_bulk_print_docs"):
		print_settings.max_bulk_print_docs = 100
		changed = True
	if not print_settings.get("max_concurrent_bulk_exports"):
		print_settings.max_concurrent_bulk_exports = 5
		changed = True
	if not changed:
		return

	print_settings.flags.ignore_mandatory = True
	print_settings.save()
