from __future__ import unicode_literals
import json
from six import iteritems
import frappe
from frappe import _
from frappe.desk.moduleview import (get_data, get_onboard_items, config_exists, get_module_link_items_from_list)

def get_modules_from_all_apps_for_user(user=None):
	if not user:
		user = frappe.session.user

	all_modules = get_modules_from_all_apps()
	user_blocked_modules = frappe.get_doc('User', user).get_blocked_modules()

	allowed_modules_list = [m for m in all_modules if m.get("module_name") not in user_blocked_modules]

	empty_tables_by_module = get_all_empty_tables_by_module()

	home_settings = frappe.db.get_value("User", frappe.session.user, 'home_settings')
	if home_settings:
		home_settings = json.loads(home_settings)

	for module in allowed_modules_list:
		module_name = module["module_name"]
		if module_name in empty_tables_by_module:
			module["onboard_present"] = 1

		if home_settings:
			category_settings = home_settings[module.get("category")] if module.get("category") else {}
			if module_name not in category_settings:
				module["hidden"] = 1
			else:
				links = category_settings[module_name]["links"]
				if links:
					module["links"] = get_module_link_items_from_list(module["app"], module_name, links.split(","))

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

	active_domains = frappe.get_active_domains()

	if isinstance(modules, dict):
		active_modules_list = []
		for m, module in iteritems(modules):
			module['module_name'] = m
			active_modules_list.append(module)
	else:
		for m in modules:
			if m.get("type") == "module" and "category" not in m:
				m["category"] = "Modules"

		# Only newly formatted modules that have a category to be shown on desk
		modules = [m for m in modules if m.get("category")]
		active_modules_list = []

		for m in modules:
			to_add = True
			module_name = m.get("module_name")

			# Check Domain
			if is_domain(m) and module_name not in active_domains:
				to_add = False

			# Check if config
			if is_module(m) and not config_exists(app, frappe.scrub(module_name)):
				to_add = False

			if "condition" in m and not m["condition"]:
				to_add = False

			if to_add:
				m["app"] = app
				active_modules_list.append(m)

	return active_modules_list

def get_all_empty_tables_by_module():
	results = frappe.db.sql("""
		SELECT
			name, module
		FROM information_schema.tables as i
		JOIN tabDocType as d
			ON i.table_name = CONCAT('tab', d.name)
		WHERE table_rows = 0;

	""")

	empty_tables_by_module = {}

	for doctype, module in results:
		if module in empty_tables_by_module:
			empty_tables_by_module[module].append(doctype)
		else:
			empty_tables_by_module[module] = [doctype]

	return empty_tables_by_module

def is_domain(module):
	return module.get("category") == "Domains"

def is_module(module):
	return module.get("type") == "module"
