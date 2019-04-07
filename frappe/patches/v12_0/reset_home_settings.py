import frappe

def execute():
	frappe.db.sql('''
		UPDATE `tabUser`
		SET `home_settings` = ''
		WHERE `user_type` = 'System User'
	''')
