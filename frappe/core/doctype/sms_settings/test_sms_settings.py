# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.sms_settings.sms_settings import (
	enforce_per_user_sms_ratelimit,
	is_permitted_to_send_sms,
	send_sms,
)
from frappe.tests import IntegrationTestCase


class TestSMSSettings(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("SMS Settings", "sms_gateway_url", "")
		frappe.db.delete("Has Role", {"parent": "SMS Settings"})

	def tearDown(self):
		frappe.db.delete("Has Role", {"parent": "SMS Settings"})
		super().tearDown()

	def test_non_auth_user_is_blocked(self):
		if not frappe.db.exists("User", "test_sms_portal_user@example.com"):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": "test_sms_portal_user@example.com",
					"first_name": "Test SMS Portal User",
					"user_type": "Website User",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)

		for user in ("Guest", "test_sms_portal_user@example.com"):
			with self.set_user(user):
				self.assertFalse(is_permitted_to_send_sms())
				self.assertRaises(frappe.PermissionError, send_sms, ["9999999999"], "hi")

	def test_role_scoping(self):
		if not frappe.db.exists("Role", "Test SMS Sender"):
			frappe.get_doc({"doctype": "Role", "role_name": "Test SMS Sender"}).insert(
				ignore_permissions=True
			)

		sms_settings = frappe.get_doc("SMS Settings")
		sms_settings.append("roles", {"role": "Test SMS Sender"})
		sms_settings.flags.ignore_mandatory = True
		sms_settings.save(ignore_permissions=True)

		self.addCleanup(lambda: frappe.get_doc("User", "test@example.com").remove_roles("Test SMS Sender"))

		with self.set_user("test@example.com"):
			frappe.get_doc("User", "test@example.com").remove_roles("Test SMS Sender")
			self.assertFalse(is_permitted_to_send_sms())
			self.assertRaises(frappe.PermissionError, send_sms, ["9999999999"], "hi")

			frappe.get_doc("User", "test@example.com").add_roles("Test SMS Sender")
			frappe.clear_cache(user="test@example.com")
			self.assertTrue(is_permitted_to_send_sms())

	def test_per_user_ratelimit(self):
		frappe.db.set_single_value("SMS Settings", "sms_rate_limit", 2)
		self.addCleanup(lambda: frappe.db.set_single_value("SMS Settings", "sms_rate_limit", None))

		self.addCleanup(lambda: frappe.cache.delete_value("sms-rate-limit", user="test@example.com"))

		with self.set_user("test@example.com"):
			frappe.cache.delete_value("sms-rate-limit", user=True)

			enforce_per_user_sms_ratelimit()
			enforce_per_user_sms_ratelimit()
			self.assertRaises(frappe.RateLimitExceededError, enforce_per_user_sms_ratelimit)
