import frappe


def execute():
	"""Fill in Print Settings bulk-export limits on sites that predate these fields."""
	frappe.reload_doctype("Print Settings")

<<<<<<< HEAD
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
=======
	# set_single_value skips doc validation, so unrelated stale values
	# (e.g. a removed pdf_generator option) can't fail this patch.
	if not frappe.db.get_single_value("Print Settings", "max_bulk_print_docs"):
		frappe.db.set_single_value("Print Settings", "max_bulk_print_docs", 100)
	if not frappe.db.get_single_value("Print Settings", "max_concurrent_bulk_exports"):
		frappe.db.set_single_value("Print Settings", "max_concurrent_bulk_exports", 5)
>>>>>>> 26b8b93 (fix(patch): don't validate Print Settings when backfilling bulk export limits)
