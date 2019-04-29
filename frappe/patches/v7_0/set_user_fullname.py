from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("Core", "DocType", "User")
	
	for user in frappe.db.get_all('User'):
		user = frappe.get_doc('User', user.name)
		user.set_full_name()
		user.db_set('full_name', user.full_name, update_modified = False)