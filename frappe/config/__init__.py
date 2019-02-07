from __future__ import unicode_literals
from frappe import _
import frappe
from frappe.desk.moduleview import get_data
from six import iteritems

def get_modules_from_all_apps_for_user(user=None):
	if not user:
		user = frappe.session.user

	all_modules = get_modules_from_all_apps()
	user_blocked_modules = frappe.get_doc('User', user).get_blocked_modules()

	allowed_modules_list = [m for m in all_modules if m.get("module_name") not in user_blocked_modules]

	return allowed_modules_list

def get_modules_from_all_apps():
	modules_list = []
	for app in frappe.get_installed_apps():
		modules_list += get_modules_from_app(app)
	return modules_list

def get_modules_from_app(app):
	try:
		modules = frappe.get_attr(app + '.config.desktop.get_data')() or {}
	except ImportError:
		return []

	# Only newly formatted modules that have a category to be shown on desk
	modules = [m for m in modules if m.get("category")]

	active_domains = frappe.get_active_domains()

	if isinstance(modules, dict):
		active_modules_list = []
		for m, module in iteritems(modules):
			module['module_name'] = m
			active_modules_list.append(module)
	else:
		active_modules_list = []
		for m in modules:
			to_add = True
			module_name = m.get("module_name")

			# Check Domain
			if is_domain(m):
				if module_name not in active_domains:
					to_add = False

			if "condition" in m and not m["condition"]:
				to_add = False

			if to_add:
				onboard_present = is_onboard_present(m) if show_onboard(m) else False
				m["onboard_present"] = onboard_present
				active_modules_list.append(m)

	return active_modules_list

def show_onboard(module):
	return module.get("type") == "module" and module.get("category") in ["Modules", "Domains"]

def is_onboard_present(module):
	print(module["module_name"])
	exists_cache = {}
	def exists(name, link_type):
		exists = exists_cache.get(name)
		if not exists:
			if link_type == "doctype" and not frappe.db.get_value('DocType', name, 'issingle'):
				exists = frappe.db.count(name)
			else:
				exists = True
			exists_cache[name] = exists
		return exists

	sections = get_data(module["module_name"], False)
	for section in sections:
		for item in section["items"]:
			if exists(item.get("name"), item.get("type")):
				return True
	return False

def is_domain(module):
	return module.get("category") == "Domains"
