import frappe
from frappe.config import get_modules_from_all_apps_for_user
import json
def execute():
	users = frappe.get_all('User', fields=['name', 'home_settings'])

	for user in users:

		if not user.home_settings:
			continue

		home_settings = json.loads(user.home_settings)

		modules_by_category = home_settings.get('modules_by_category')
		if not modules_by_category:
			continue
		visible_modules = []
		category_to_check = []

		for category, modules in modules_by_category.items():
			visible_modules += modules
			category_to_check.append(category)

		all_modules = get_modules_from_all_apps_for_user(user.name)
		all_modules = set([m.get('name') or m.get('module_name') or m.get('label') \
			for m in all_modules if m.get('category') in category_to_check])

		hidden_modules = home_settings.get("hidden_modules", [])

		modules_in_home_settings = set(visible_modules + hidden_modules)

		all_modules = all_modules.union(modules_in_home_settings)

		missing_modules = all_modules - modules_in_home_settings

		if missing_modules:
			home_settings['hidden_modules'] = hidden_modules + list(missing_modules)
			home_settings = json.dumps(home_settings)
			frappe.set_value('User', user.name, 'home_settings', home_settings)

	frappe.cache().delete_key('home_settings')
