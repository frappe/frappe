import frappe, json

from frappe.desk.doctype.desktop_icon.desktop_icon import sync_from_app, get_user_copy
import frappe.defaults

def execute():
	frappe.reload_doc('desk', 'doctype', 'desktop_icon')

	frappe.db.sql('delete from `tabDesktop Icon`')

	modules_list = []
	for app in frappe.get_installed_apps():
		modules_list += sync_from_app(app)

	# sync hidden modules
	hidden_modules = frappe.db.get_global('hidden_modules')
	if hidden_modules:
		for m in json.loads(hidden_modules):
			try:
				desktop_icon = frappe.get_doc('Desktop Icon', {'module_name': m, 'standard': 1, 'app': app})
				desktop_icon.db_set('hidden', 1)
			except frappe.DoesNotExistError:
				pass

	# sync user sort
	for user in frappe.get_all('User', filters={'user_type': 'System User'}):
		user_list = frappe.defaults.get_user_default('_user_desktop_items', user=user.name)
		if user_list:
			user_list = json.loads(user_list)
			for i, module_name in enumerate(user_list):
				try:
					desktop_icon = get_user_copy(module_name, user=user.name)
					desktop_icon.db_set('idx', i)
				except frappe.DoesNotExistError:
					pass

			# set remaining icons as hidden
			for module_name in list(set([m['module_name'] for m in modules_list]) - set(user_list)):
				try:
					desktop_icon = get_user_copy(module_name, user=user.name)
					desktop_icon.db_set('hidden', 1)
				except frappe.DoesNotExistError:
					pass
