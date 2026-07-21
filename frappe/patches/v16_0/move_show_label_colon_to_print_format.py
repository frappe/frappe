import frappe


def execute():
	"""
	"Show Colon After Field Labels" moved from Print Settings to Print Format,
	so it can be chosen per format instead of for the whole site.

	Runs pre-model-sync, while the old value is still readable: reload Print Format
	first so its new column exists, then carry the value across so sites that had
	it on keep the colons they had.
	"""
	# Print Settings is a Single, so the old value lives in tabSingles
	if not frappe.db.get_single_value("Print Settings", "show_label_colon"):
		return

	frappe.reload_doc("printing", "doctype", "print_format")
	frappe.db.set_value("Print Format", {"disabled": 0}, "show_label_colon", 1, update_modified=False)
