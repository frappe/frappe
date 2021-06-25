import frappe


def execute():
	if frappe.db.exists("DocType", "Client Script"):
		return

	frappe.rename_doc("DocType", "Custom Script", "Client Script")
	frappe.reload_doctype("Client Script", force=True)
