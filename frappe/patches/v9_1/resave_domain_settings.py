import frappe

def execute():
	try:
		frappe.get_single('Domain Settings').save()
	except frappe.LinkValidationError:
		pass