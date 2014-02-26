import frappe

def execute():
	if frappe.db.exists("Website Route", "index"):
		frappe.delete_doc("Website Route", "index", ignore_permissions=True)
	