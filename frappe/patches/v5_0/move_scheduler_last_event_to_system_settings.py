import frappe

def execute():
	frappe.reload_doctype('System Settings')
	last = frappe.db.get_global('scheduler_last_event')
	frappe.db.set_value('System Settings', 'System Settings', 'scheduler_last_event', last)

