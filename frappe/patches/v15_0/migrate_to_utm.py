import frappe


def execute():
	"""
	Rename the Marketing Campaign table to UTM Campaign table
	"""
	if frappe.db.exists("DocType", "UTM Campaign"):
		return

	if not frappe.db.exists("DocType", "Marketing Campaign"):
		return

	frappe.rename_doc("DocType", "Marketing Campaign", "UTM Campaign", force=True)
	frappe.reload_doctype("UTM Campaign", force=True)
