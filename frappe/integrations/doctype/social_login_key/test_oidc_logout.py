# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib.parse import parse_qs, urlparse

import frappe
from frappe.tests import IntegrationTestCase


class TestOIDCLogout(IntegrationTestCase):
	def test_keycloak_template_has_disabled_oidc_logout(self):
		key = make_social_login_key(social_login_provider="Keycloak")
		key.get_social_login_provider("Keycloak", initialize=True)

		self.assertEqual(key.end_session_endpoint, "/protocol/openid-connect/logout")
		self.assertFalse(key.enable_oidc_logout)

	def test_oidc_logout_requires_endpoints(self):
		key = make_oidc_social_login_key(end_session_endpoint=None)
		with self.assertRaisesRegex(frappe.ValidationError, "End Session Endpoint"):
			key.validate()

		key.end_session_endpoint = "/logout"
		key.post_logout_redirect_uri = None
		with self.assertRaisesRegex(frappe.ValidationError, "Post Logout Redirect URI"):
			key.validate()

	def test_oidc_logout_resolves_relative_end_session_endpoint(self):
		key = make_oidc_social_login_key(end_session_endpoint="/logout")

		key.validate()

		self.assertEqual(key.get_end_session_endpoint(), "https://id.example.com/realms/test/logout")

	def test_oidc_logout_rejects_non_https_urls(self):
		key = make_oidc_social_login_key(end_session_endpoint="http://id.example.com/logout")
		with self.assertRaises(frappe.ValidationError):
			key.validate()

		key.end_session_endpoint = "/logout"
		key.post_logout_redirect_uri = "http://site.example.com/login"
		with self.assertRaises(frappe.ValidationError):
			key.validate()

	def test_oidc_logout_url_uses_client_id_and_registered_redirect(self):
		key = make_oidc_social_login_key()

		key.validate()
		logout_url = urlparse(key.get_oidc_logout_url())

		self.assertEqual(logout_url.scheme, "https")
		self.assertEqual(logout_url.netloc, "id.example.com")
		self.assertEqual(logout_url.path, "/realms/test/logout")
		self.assertEqual(
			parse_qs(logout_url.query),
			{
				"client_id": ["test-client"],
				"post_logout_redirect_uri": ["https://site.example.com/login"],
			},
		)

	def test_oidc_logout_replaces_duplicate_configured_parameters(self):
		key = make_oidc_social_login_key(
			end_session_endpoint=(
				"/logout?client_id=untrusted"
				"&post_logout_redirect_uri=https%3A%2F%2Fwrong.example.com%2F"
				"&ui_locales=en"
			)
		)

		key.validate()
		query = parse_qs(urlparse(key.get_oidc_logout_url()).query)

		self.assertEqual(query["client_id"], ["test-client"])
		self.assertEqual(query["post_logout_redirect_uri"], ["https://site.example.com/login"])
		self.assertEqual(query["ui_locales"], ["en"])


def make_social_login_key(**kwargs):
	kwargs["doctype"] = "Social Login Key"
	kwargs.setdefault("provider_name", "Test OIDC Provider")
	return frappe.get_doc(kwargs)


def make_oidc_social_login_key(**kwargs):
	values = {
		"base_url": "https://id.example.com/realms/test",
		"custom_base_url": 1,
		"authorize_url": "/authorize",
		"access_token_url": "/token",
		"redirect_url": "/oauth/callback",
		"enable_social_login": 0,
		"client_id": "test-client",
		"enable_oidc_logout": 1,
		"end_session_endpoint": "/logout",
		"post_logout_redirect_uri": "https://site.example.com/login",
	}
	values.update(kwargs)
	return make_social_login_key(**values)
