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
	global_blocked_modules = frappe.get_doc('User', 'Administrator').get_blocked_modules()
	user_blocked_modules = frappe.get_doc('User', user).get_blocked_modules()
	blocked_modules = global_blocked_modules + user_blocked_modules
	allowed_modules_list = [m for m in all_modules if m.get("module_name") not in blocked_modules]

	empty_tables_by_module = get_all_empty_tables_by_module()

	for module in allowed_modules_list:
		module_name = module.get("module_name")

		# Apply onboarding status
		if module_name in empty_tables_by_module:
			module["onboard_present"] = 1

		# Set defaults links
		module["links"] =  get_onboard_items(module["app"], frappe.scrub(module_name))[:5]

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
			module['app'] = app
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
	empty_tables = set(r[0] for r in frappe.db.multisql({
		"mariadb": """
			SELECT table_name
			FROM information_schema.tables
			WHERE table_rows = 0 and table_schema = "{}"
			""".format(frappe.conf.db_name),
		"postgres": """
			SELECT "relname" as "table_name"
			FROM "pg_stat_all_tables"
			WHERE n_tup_ins = 0
		"""
	}))

	results = frappe.get_all("DocType", fields=["name", "module"])
	empty_tables_by_module = {}

	for doctype, module in results:
		if "tab" + doctype in empty_tables:
			if module in empty_tables_by_module:
				empty_tables_by_module[module].append(doctype)
			else:
				empty_tables_by_module[module] = [doctype]
	return empty_tables_by_module

def is_domain(module):
	return module.get("category") == "Domains"

def is_module(module):
	return module.get("type") == "module"
