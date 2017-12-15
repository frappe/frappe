# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe
from frappe.core.page.permission_manager.permission_manager import get_roles_and_doctypes
from frappe.desk.doctype.desktop_icon.desktop_icon import (get_desktop_icons, add_user_icon,
	clear_desktop_icons_cache)

from frappe.core.doctype.domain_settings.domain_settings import get_active_modules

class TestDomainification(unittest.TestCase):
	def setUp(self):
		# create test domain
		self.new_domain("_Test Domain 1")
		self.new_domain("_Test Domain 2")

		self.remove_from_active_domains(remove_all=True)
		self.add_active_domain("_Test Domain 1")

	def tearDown(self):
		frappe.db.sql("delete from tabRole where name='_Test Role'")
		frappe.db.sql("delete from `tabHas Role` where role='_Test Role'")
		frappe.db.sql("delete from tabDomain where name in ('_Test Domain 1', '_Test Domain 2')")
		frappe.delete_doc('DocType', 'Test Domainification')
		self.remove_from_active_domains(remove_all=True)

	def add_active_domain(self, domain):
		""" add domain in active domain """

		if not domain:
			return

		domain_settings = frappe.get_doc("Domain Settings", "Domain Settings")
		domain_settings.append("active_domains", { "domain": domain })
		domain_settings.save()

	def remove_from_active_domains(self, domain=None, remove_all=False):
		""" remove domain from domain settings """
		if not (domain or remove_all):
			return

		domain_settings = frappe.get_doc("Domain Settings", "Domain Settings")

		if remove_all:
			domain_settings.set("active_domains", [])
		else:
			to_remove = []
			[ to_remove.append(row) for row in domain_settings.active_domains if row.domain == domain ]
			[ domain_settings.remove(row) for row in to_remove ]

		domain_settings.save()

	def new_domain(self, domain):
		# create new domain
		frappe.get_doc({
			"doctype": "Domain",
			"domain": domain
		}).insert()

	def new_doctype(self, name):
		return frappe.get_doc({
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"fields": [{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Data"}],
			"permissions": [{"role": "System Manager", "read": 1}],
			"name": name
		})

	def test_active_domains(self):
		self.assertTrue("_Test Domain 1" in frappe.get_active_domains())
		self.assertFalse("_Test Domain 2" in frappe.get_active_domains())

		self.add_active_domain("_Test Domain 2")
		self.assertTrue("_Test Domain 2" in frappe.get_active_domains())

		self.remove_from_active_domains("_Test Domain 1")
		self.assertTrue("_Test Domain 1" not in frappe.get_active_domains())

	def test_doctype_and_role_domainification(self):
		"""
			test if doctype is hidden if the doctype's restrict to domain is not included
			in active domains
		"""

		test_doctype = self.new_doctype("Test Domainification")
		test_doctype.insert()

		test_role = frappe.get_doc({
			"doctype": "Role",
			"role_name": "_Test Role"
		}).insert()

		# doctype should be hidden in desktop icon, role permissions
		results = get_roles_and_doctypes()
		self.assertTrue("Test Domainification" in [d.get("value") for d in results.get("doctypes")])
		self.assertTrue("_Test Role" in [d.get("value") for d in results.get("roles")])

		self.add_active_domain("_Test Domain 2")
		test_doctype.restrict_to_domain = "_Test Domain 2"
		test_doctype.save()

		test_role.restrict_to_domain = "_Test Domain 2"
		test_role.save()

		results = get_roles_and_doctypes()
		self.assertTrue("Test Domainification" in [d.get("value") for d in results.get("doctypes")])
		self.assertTrue("_Test Role" in [d.get("value") for d in results.get("roles")])

		self.remove_from_active_domains("_Test Domain 2")
		results = get_roles_and_doctypes()

		self.assertTrue("Test Domainification" not in [d.get("value") for d in results.get("doctypes")])
		self.assertTrue("_Test Role" not in [d.get("value") for d in results.get("roles")])

	def test_desktop_icon_for_domainification(self):
		""" desktop icon should be hidden if doctype's restrict to domain is not in active domains """

		test_doctype = self.new_doctype("Test Domainification")
		test_doctype.restrict_to_domain = "_Test Domain 2"
		test_doctype.insert()

		self.add_active_domain("_Test Domain 2")
		add_user_icon('Test Domainification')

		icons = get_desktop_icons()

		doctypes = [icon.get("_doctype") for icon in icons if icon.get("_doctype") == "Test Domainification" \
			and icon.get("blocked") == 0]
		self.assertTrue("Test Domainification" in doctypes)

		# doctype should be hidden from the desk
		self.remove_from_active_domains("_Test Domain 2")
		clear_desktop_icons_cache()		# clear cache to fetch the desktop icon according to new active domains
		icons = get_desktop_icons()

		doctypes = [icon.get("_doctype") for icon in icons if icon.get("_doctype") == "Test Domainification" \
			and icon.get("blocked") == 0]
		self.assertFalse("Test Domainification" in doctypes)

	def test_module_def_for_domainification(self):
		""" modules should be hidden if module def's restrict to domain is not in active domains"""

		test_module_def = frappe.get_doc("Module Def", "Contacts")
		test_module_def.restrict_to_domain = "_Test Domain 2"
		test_module_def.save()

		self.add_active_domain("_Test Domain 2")

		modules = get_active_modules()
		self.assertTrue("Contacts" in modules)

		# doctype should be hidden from the desk
		self.remove_from_active_domains("_Test Domain 2")
		modules = get_active_modules()
		self.assertTrue("Contacts" not in modules)

		test_module_def = frappe.get_doc("Module Def", "Contacts")
		test_module_def.restrict_to_domain = ""
		test_module_def.save()
