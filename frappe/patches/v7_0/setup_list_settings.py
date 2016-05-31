from frappe.installer import create_list_settings_table
from frappe.model.utils.list_settings import update_list_settings
import frappe, json

def execute():
	create_list_settings_table()

	for user in frappe.db.get_all('User', {'user_type': 'System User'}):
		defaults = frappe.defaults.get_defaults_for(user.name)
		for key, value in defaults.iteritems():
			if key.startswith('_list_settings:'):
				doctype = key.replace('_list_settings:', '')
				columns = ['`tab{1}`.`{0}`'.format(*c) for c in json.loads(value)]

				update_list_settings(doctype, {'fields': columns})

