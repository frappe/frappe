# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.integrations.utils import OAuth2DynamicClientMetadata, validate_dynamic_client_metadata
from frappe.tests import UnitTestCase


class TestOAuth2DynamicClientMetadata(UnitTestCase):
	@patch.dict(frappe.conf, {"developer_mode": 0})
	def test_redirect_uri_scheme(self):
		for redirect_uri in (
			"https://example.com/callback",
			"http://127.0.0.1:8080/callback",
			"http://127.42.0.9/callback",
			"http://[::1]:8080/callback",
		):
			with self.subTest(redirect_uri=redirect_uri):
				client = OAuth2DynamicClientMetadata(client_name="Test Client", redirect_uris=[redirect_uri])
				self.assertIsNone(validate_dynamic_client_metadata(client))

		for redirect_uri in (
			"http://example.com/callback",
			"http://localhost/callback",
			"http://192.168.1.1/callback",
		):
			with self.subTest(redirect_uri=redirect_uri):
				client = OAuth2DynamicClientMetadata(client_name="Test Client", redirect_uris=[redirect_uri])
				self.assertEqual(validate_dynamic_client_metadata(client), "redirect_uris must be https")
