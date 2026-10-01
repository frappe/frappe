# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase


class TestSystemSettings(IntegrationTestCase):
	def test_only_administrator_can_lock_admin_password_login(self):
		frappe.set_user("test@example.com")
		self.addCleanup(frappe.set_user, "Administrator")

		settings = frappe.get_doc("System Settings")
		settings.disable_administrator_password_login = 1
		with self.assertRaises(frappe.PermissionError):
			settings.save(ignore_permissions=True)
