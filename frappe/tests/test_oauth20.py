# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe, requests
from frappe.utils import get_url
from frappe.test_runner import make_test_records

class TestOAuth20(unittest.TestCase):
	def setUp(self):
		# Create Client
		make_test_records("OAuth Client")

	def test_authorize_guest_redirect(self):
		resp = requests.get(
				frappe.get_site_config().host_name + 
				"/api/method/frappe.integrations.oauth2.authorize?" + 
				"client_id=test_client_id&" + 
				"scope=all%20openid&" +
				"response_type=code&" + 
				"redirect_uri=http%3A%2F%2Flocalhost"
			)
		self.assertTrue(resp.history[0].status_code == 302)
		self.assertTrue(resp.status_code == 200)
