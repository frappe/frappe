# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.permissions import has_app_permission
from flow.tests.test_ai_api import OTHER, _ensure_user
from flow.www.flow import index


class TestFlowPage(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_guest_is_sent_to_login_and_back(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			index.get_context(frappe._dict())
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/flow")

	def test_the_page_carries_what_the_app_boots_from(self):
		context = index.get_context(frappe._dict())
		boot = context.boot
		self.assertTrue(boot["csrf_token"])
		self.assertEqual(boot["site_name"], frappe.local.site)
		self.assertIn("socketio_port", boot)
		self.assertEqual(boot["flow_boot"]["user"]["name"], "Administrator")
		self.assertIn("agents", boot["flow_boot"])

	def test_the_dev_boot_needs_developer_mode(self):
		with patch.dict(frappe.local.conf, {"developer_mode": 0}):
			with self.assertRaises(frappe.PermissionError):
				index.get_context_for_dev()
		with patch.dict(frappe.local.conf, {"developer_mode": 1}):
			self.assertIn("flow_boot", index.get_context_for_dev())

	def test_the_apps_screen_lists_flow_for_flow_users_only(self):
		self.assertTrue(has_app_permission())
		frappe.set_user(_ensure_user(OTHER))
		self.assertTrue(has_app_permission())
		nobody = "page-nobody@example.com"
		if not frappe.db.exists("User", nobody):
			frappe.get_doc(
				{"doctype": "User", "email": nobody, "first_name": "Nobody", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		frappe.set_user(nobody)
		self.assertFalse(has_app_permission())
