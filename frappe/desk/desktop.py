# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
# Author - Shivam Mishra <shivam@frappe.io>

from __future__ import unicode_literals
import frappe
import json
from frappe import _

@frappe.whitelist()
def get_desktop_settings():
	# from frappe.config import get_modules_from_all_apps_for_user
	# all_modules = get_modules_from_all_apps_for_user()

	query = """SELECT parent from `tabDocPerm` where `role` in ({})""".format(", ".join(["%s"]*len(frappe.get_roles())))
	standard_permissions = [item[0] for item in frappe.db.sql(query, frappe.get_roles())]

	query = """SELECT parent from `tabCustom DocPerm` where `role` in ({})""".format(", ".join(["%s"]*len(frappe.get_roles())))
	custom_permissions = [item[0] for item in frappe.db.sql(query, frappe.get_roles())]

	all_doctypes = standard_permissions + custom_permissions
	modules = []

	for doctype in all_doctypes:
		modules.append(frappe.db.get_value("DocType", doctype, 'module'))

	return set(modules)

@frappe.whitelist()
def get_modules_doctpes_and_reports():
	from collections import defaultdict

	# Query all doctypes and reports
	doctypes = frappe.db.sql("SELECT name, module from `tabDocType`", as_dict=1)
	reports = frappe.db.sql("SELECT name, module from `tabReport`", as_dict=1)

	all_data = doctypes + reports

	# filter based on restricted domains
	active_domains = frappe.get_active_domains();
	modules_query ="""
		SELECT name, restrict_to_domain
		FROM `tabModule Def`
		WHERE
			`restrict_to_domain` IN ({}) OR
			`restrict_to_domain` IS NULL
		""".format(", ".join(["%s"]*len(active_domains)))

	active_modules_based_on_domains = tuple([item[0] for item in frappe.db.sql(modules_query, active_domains)])

	grouped = defaultdict(list)
	for item in all_data:
		if item['module'] in active_modules_based_on_domains or True:
			grouped[item['module']].append(item['name'])

	return grouped

@frappe.whitelist()
def get_base_configuration_for_desk():
	import time
	pages = [frappe.get_doc("Desk Page", item['name']) for item in frappe.get_all("Desk Page")]
	time.sleep(3)
	return pages

