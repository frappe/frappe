import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'user')
	frappe.db.sql('''
		UPDATE `tabUser`
		SET `home_settings` = ''
		WHERE `user_type` = 'System User'
	''')
