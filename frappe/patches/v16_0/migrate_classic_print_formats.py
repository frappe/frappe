import frappe


def execute():
	"""Convert every classic print-format-builder format to the new builder's
	layout. The original classic array is kept in `classic_format_data`, so the
	patch is re-runnable and a conversion can be rolled back."""
	from frappe.printing.doctype.print_format.classic_converter import migrate_all_classic_formats

	report = migrate_all_classic_formats()
	for name, dropped in report.items():
		if dropped:
			frappe.log_error(
				title=f"Print Format conversion dropped fields: {name}",
				message=f"Fields no longer in the DocType, removed from the layout: {', '.join(dropped)}",
			)

	frappe.delete_doc_if_exists("Page", "print-format-builder-classic", force=1)
