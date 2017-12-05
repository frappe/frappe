import frappe

def execute():
	for user_name in frappe.get_all('User', filters={'user_type': 'Website User'}):
		user = frappe.get_doc('User', user_name)
		if user.roles:
			user.roles = []
			user.save()
