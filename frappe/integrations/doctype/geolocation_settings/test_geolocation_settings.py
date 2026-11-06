# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import requests

import frappe
from frappe.integrations.doctype.geolocation_settings.geolocation_settings import autocomplete
from frappe.tests import IntegrationTestCase


class TestGeolocationSettings(IntegrationTestCase):
	@IntegrationTestCase.change_settings(
		"Geolocation Settings",
		{"enable_address_autocompletion": 1, "provider": "Geoapify", "api_key": "secret-key-123"},
	)
	def test_autocomplete_provider_error_hides_api_key(self):
		error = requests.HTTPError(
			"500 Server Error for url: https://api.geoapify.com/?apiKey=secret-key-123"
		)
		with patch("requests.get", side_effect=error):
			with self.assertRaises(frappe.ValidationError) as ctx:
				autocomplete("main street")

		self.assertNotIn("secret-key-123", str(ctx.exception))
		self.assertIsNone(ctx.exception.__cause__)
		self.assertTrue(ctx.exception.__suppress_context__)
