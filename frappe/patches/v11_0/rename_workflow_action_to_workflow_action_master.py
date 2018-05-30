import frappe

def execute():
	if not frappe.db.table_exists("Workflow Action Master"):
		frappe.db.sql("RENAME TABLE `tabWorkflow Action` to `tabWorkflow Action Master`")
