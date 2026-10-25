import frappe


def execute():
	"""Fill in Print Settings bulk-export limits on sites that predate these fields."""
	frappe.reload_doctype("Print Settings")

	# set_single_value skips doc validation, so unrelated stale values
	# (e.g. a removed pdf_generator option) can't fail this patch.
	if not frappe.db.get_single_value("Print Settings", "max_bulk_print_docs"):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 100)
	if not frappe.db.get_single_value("Print Settings", "max_concurrent_bulk_exports"):
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 5)
