from unittest.mock import patch

import requests

import frappe
from frappe.integrations.frappe_providers.frappecloud_billing import current_site_info
from frappe.tests.utils import FrappeTestCase


class TestFrappeCloudBilling(FrappeTestCase):
	@patch.dict(frappe.conf, {"fc_communication_secret": "secret"})
	@patch("requests.post", side_effect=requests.exceptions.SSLError)
	def test_current_site_info_ignores_network_errors(self, _):
		frappe.cache().delete_value(f"fc_current_site_info:{frappe.local.site}")
		self.assertIsNone(current_site_info())
