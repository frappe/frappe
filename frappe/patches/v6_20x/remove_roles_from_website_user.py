from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "user_email")
	frappe.reload_doc("core", "doctype", "user")
	for user_name in frappe.get_all('User', filters={'user_type': 'Website User'}):
		user = frappe.get_doc('User', user_name)
		if user.roles:
			user.roles = []
			user.save()
