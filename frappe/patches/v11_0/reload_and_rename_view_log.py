import frappe

def execute():
	if frappe.db.exists('DocType', 'View log'):
		frappe.reload_doc('core', 'doctype', 'view_log', force=True)
		frappe.db.sql("INSERT INTO `tabView Log` SELECT * from `tabView log`")
		frappe.delete_doc('DocType', 'View log')
		frappe.reload_doc('core', 'doctype', 'view_log', force=True)
	else:
		frappe.reload_doc('core', 'doctype', 'view_log')
