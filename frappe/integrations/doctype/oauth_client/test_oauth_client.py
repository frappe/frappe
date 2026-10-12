# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.integrations.doctype.oauth_client.oauth_client import delete_unused_dynamic_clients
from frappe.integrations.oauth2 import register_client
from frappe.integrations.utils import OAuth2DynamicClientMetadata, create_new_oauth_client
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime


class TestOAuthClient(IntegrationTestCase):
	def create_dynamic_client(self):
		return create_new_oauth_client(
			OAuth2DynamicClientMetadata(
				client_name="Test Dynamic Client",
				redirect_uris=["https://example.com/oauth/callback"],
			)
		)

	def test_generates_strong_client_secret(self):
		client = frappe.new_doc("OAuth Client")

		client.validate()

		self.assertGreaterEqual(len(client.client_secret), 56)

	def test_dynamic_registration_marks_client(self):
		client = self.create_dynamic_client()

		self.assertTrue(client.is_dynamic_client)
		self.assertEqual(client.token_endpoint_auth_method, "Client Secret Basic")

	def test_deletes_unused_dynamic_client_after_grace_period(self):
		client = self.create_dynamic_client()
		frappe.db.set_value(
			"OAuth Client",
			client.name,
			"creation",
			add_to_date(now_datetime(), minutes=-11),
			update_modified=False,
		)

		delete_unused_dynamic_clients()

		self.assertFalse(frappe.db.exists("OAuth Client", client.name))

	def test_preserves_dynamic_client_that_issued_token(self):
		client = self.create_dynamic_client()
		frappe.db.set_value(
			"OAuth Client",
			client.name,
			"creation",
			add_to_date(now_datetime(), minutes=-11),
			update_modified=False,
		)
		frappe.get_doc(
			{
				"doctype": "OAuth Bearer Token",
				"access_token": frappe.generate_hash(),
				"client": client.name,
				"expires_in": 3600,
				"scopes": "openid",
				"status": "Active",
				"user": "Administrator",
			}
		).insert(ignore_permissions=True)

		delete_unused_dynamic_clients()

		self.assertTrue(frappe.db.exists("OAuth Client", client.name))

	def test_dynamic_registration_is_rate_limited_by_ip(self):
		request_ip = "192.0.2.1"
		original_request = getattr(frappe.local, "request", None)
		original_request_ip = getattr(frappe.local, "request_ip", None)
		original_form_dict = getattr(frappe.local, "form_dict", None)
		frappe.local.request_ip = request_ip
		frappe.local.request = frappe._dict(
			method="POST",
			json={
				"client_name": "Rate Limited Dynamic Client",
				"redirect_uris": ["https://example.com/oauth/callback"],
			},
		)
		frappe.local.form_dict = frappe._dict(cmd="frappe.integrations.oauth2.register_client")
		frappe.db.set_single_value("OAuth Settings", "enable_dynamic_client_registration", 1)
		frappe.clear_cache(doctype="OAuth Settings")
		rate_limit_key = (
			frappe.cache.make_key(f"rl:frappe.integrations.oauth2.register_client:{request_ip}") + b":600"
		)
		frappe.cache.delete(rate_limit_key)

		try:
			for _ in range(5):
				response = register_client()
				self.assertEqual(response.status_code, 201)
			self.assertRaises(frappe.RateLimitExceededError, register_client)
		finally:
			frappe.cache.delete(rate_limit_key)
			frappe.local.request = original_request
			frappe.local.request_ip = original_request_ip
			frappe.local.form_dict = original_form_dict
			frappe.clear_cache(doctype="OAuth Settings")
