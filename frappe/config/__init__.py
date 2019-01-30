from __future__ import unicode_literals
from frappe import _
import frappe
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
		for m, desktop_icon in iteritems(modules):
			desktop_icon['module_name'] = m
			active_modules_list.append(desktop_icon)
	else:
		active_modules_list = []
		for m in modules:
			to_add = True
			module_name = m.get("module_name")

			# Check Domain
			if is_domain(m):
				if module_name not in active_domains:
					to_add = False

			if to_add:
				active_modules_list.append(m)

	return active_modules_list

def is_domain(module):
	return module.get("category") == "Domains"
