from unittest.mock import MagicMock, patch

import requests

import frappe
from frappe.integrations.frappe_providers.frappecloud_billing import current_site_info
from frappe.tests import IntegrationTestCase


class TestFrappeCloudBilling(IntegrationTestCase):
	@patch.dict(frappe.conf, {"fc_communication_secret": "secret"})
	@patch("requests.post", side_effect=requests.exceptions.SSLError)
	def test_current_site_info_ignores_network_errors(self, _):
		frappe.cache().delete_value(f"fc_current_site_info:{frappe.local.site}")
		self.assertIsNone(current_site_info())

	@patch.dict(frappe.conf, {"fc_communication_secret": "secret"})
	@patch("requests.post", return_value=MagicMock(status_code=500))
	def test_current_site_info_does_not_cache_failed_responses(self, _):
		cache_key = f"fc_current_site_info:{frappe.local.site}"
		frappe.cache().delete_value(cache_key)
		self.assertIsNone(current_site_info())
		self.assertIsNone(frappe.cache().get_value(cache_key))
