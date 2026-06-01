import frappe


def execute():
	"""
	The "beta" Print Format Builder is now the default builder and lives at
	/app/print-format-builder. The old jQuery builder has been moved to
	/app/print-format-builder-classic. Drop the orphan Page docs left behind
	by the rename so users do not see broken sidebar entries.
	"""
	frappe.delete_doc_if_exists("Page", "print-format-builder-beta", force=1)
