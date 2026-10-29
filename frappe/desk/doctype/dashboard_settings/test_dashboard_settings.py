# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.desk.doctype.dashboard_settings.dashboard_settings import create_dashboard_settings
from frappe.tests import IntegrationTestCase


class TestDashboardSettings(IntegrationTestCase):
	def make_user(self, email, roles=("Blogger",), user_type="System User"):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Test",
				"user_type": user_type,
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "User", email, force=True, ignore_missing=True)
		return email

	def test_create_dashboard_settings_only_for_the_session_user(self):
		user = self.make_user("settings_user@example.com")
		other = self.make_user("settings_other@example.com")

		with self.set_user(user), patch.object(frappe.db, "commit"):
			self.assertRaises(frappe.PermissionError, create_dashboard_settings, other)
			self.assertEqual(create_dashboard_settings(user).name, user)
