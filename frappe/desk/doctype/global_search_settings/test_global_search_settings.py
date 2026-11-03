# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	reset_global_search_settings_doctypes,
)
from frappe.tests.utils import FrappeTestCase


class TestGlobalSearchSettings(FrappeTestCase):
	def test_reset_requires_write_permission(self):
		with test_user(roles=["Desk User"]) as user, self.set_user(user.name):
			self.assertRaises(frappe.PermissionError, reset_global_search_settings_doctypes)

		with test_user(roles=["System Manager"]) as user, self.set_user(user.name):
			reset_global_search_settings_doctypes()
