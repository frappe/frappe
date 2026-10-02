# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase


class TestSystemSettings(IntegrationTestCase):
	def test_only_administrator_can_lock_admin_password_login(self):
		self.addCleanup(frappe.set_user, "Administrator")

		# System Manager can save the doc, but permlevel 1 silently resets the field
		frappe.set_user("test@example.com")
		settings = frappe.get_doc("System Settings")
		before = settings.disable_administrator_password_login
		settings.disable_administrator_password_login = not settings.disable_administrator_password_login
		settings.save()
		self.assertEqual(settings.disable_administrator_password_login, before)

		# without System Manager role, write on the doctype throws a permission error
		frappe.set_user("testperm@example.com")
		settings = frappe.get_doc("System Settings")
		settings.disable_administrator_password_login = not settings.disable_administrator_password_login
		with self.assertRaises(frappe.PermissionError):
			settings.save()
