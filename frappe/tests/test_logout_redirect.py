# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.handler import get_post_logout_redirect, logout
from frappe.tests import IntegrationTestCase


class TestPostLogoutRedirect(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.local.flags.pop("post_logout_redirect", None)
		self.addCleanup(frappe.local.flags.pop, "post_logout_redirect", None)

	def test_site_relative_redirect(self):
		frappe.local.flags.post_logout_redirect = "/login?logged_out=1"
		self.assertEqual(get_post_logout_redirect(), "/login?logged_out=1")
		self.assertIsNone(get_post_logout_redirect())

	def test_absolute_https_redirect(self):
		redirect = "https://id.example.com/realms/test/protocol/openid-connect/logout?client_id=frappe"
		frappe.local.flags.post_logout_redirect = redirect
		self.assertEqual(get_post_logout_redirect(), redirect)

	def test_unsafe_redirects_are_ignored(self):
		invalid_urls = (
			"//evil.example.com/logout",
			"/\\evil.example.com/logout",
			"http://id.example.com/logout",
			"javascript:alert(1)",
			"https://user:password@id.example.com/logout",
			"https://@id.example.com/logout",
			"https://id.example.com:notaport/logout",
			"https://id.example.com:65536/logout",
			" https://id.example.com/logout",
			"https://[invalid",
			"/login\nLocation: https://evil.example.com",
			"login",
			123,
		)
		for redirect in invalid_urls:
			with self.subTest(redirect=redirect):
				frappe.local.flags.post_logout_redirect = redirect
				self.assertIsNone(get_post_logout_redirect())
				self.assertIsNone(frappe.local.flags.get("post_logout_redirect"))

	def test_hook_redirect_overrides_oidc_redirect(self):
		def on_logout():
			frappe.local.flags.post_logout_redirect = "https://id.example.com/logout"

		with (
			patch("frappe.utils.oauth.get_oauth2_logout_url", return_value="https://oidc.example.com/logout"),
			patch.object(frappe.local.login_manager, "logout", side_effect=on_logout),
			patch.object(frappe.db, "commit"),
		):
			self.assertEqual(logout(), "https://id.example.com/logout")

	def test_oidc_redirect_remains_fallback_when_no_hook_redirect(self):
		with (
			patch("frappe.utils.oauth.get_oauth2_logout_url", return_value="https://oidc.example.com/logout"),
			patch.object(frappe.local.login_manager, "logout"),
			patch.object(frappe.db, "commit"),
		):
			self.assertEqual(logout(), "https://oidc.example.com/logout")

	def test_invalid_hook_redirect_does_not_prevent_logout(self):
		def on_logout():
			frappe.local.flags.post_logout_redirect = "javascript:alert(1)"

		with (
			patch("frappe.utils.oauth.get_oauth2_logout_url", return_value=None),
			patch.object(frappe.local.login_manager, "logout", side_effect=on_logout) as manager_logout,
			patch.object(frappe.db, "commit") as commit,
		):
			self.assertIsNone(logout())
			manager_logout.assert_called_once()
			commit.assert_called_once()

	def test_stale_redirect_is_not_reused(self):
		frappe.local.flags.post_logout_redirect = "https://old.example.com/logout"
		with (
			patch("frappe.utils.oauth.get_oauth2_logout_url", return_value=None),
			patch.object(frappe.local.login_manager, "logout"),
			patch.object(frappe.db, "commit"),
		):
			self.assertIsNone(logout())
