# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.desk.doctype.dashboard_settings.dashboard_settings import create_dashboard_settings
from frappe.tests import IntegrationTestCase


class TestDashboardSettings(IntegrationTestCase):
	def test_create_dashboard_settings_only_for_the_session_user(self):
		with (
			test_user(roles=["Desk User"]) as user,
			test_user(roles=["Desk User"]) as other,
			self.set_user(user.name),
			patch.object(frappe.db, "commit"),
		):
			self.assertRaises(frappe.PermissionError, create_dashboard_settings, other.name)
			self.assertEqual(create_dashboard_settings(user.name).name, user.name)
