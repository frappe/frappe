# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe, os
from frappe.utils import get_url
from frappe.test_runner import make_test_records
from werkzeug.test import Client
from frappe.app import application
from werkzeug.wrappers import BaseResponse

class TestOAuth20(unittest.TestCase):
	def setUp(self):
		# Create Client
		make_test_records("OAuth Client")

	def test_authorize_guest_redirect(self):
		expect_in_resp_data = "/login?redirect-to=/api/method/frappe.integrations.oauth2.authorize?" 
		expect_in_resp_data += "redirect_uri%3Dhttp%253A%252F%252Flocalhost%26" 
		expect_in_resp_data += "response_type%3Dcode%26"
		expect_in_resp_data += "client_id%3Dtest_client_id%26" 
		expect_in_resp_data += "scope%3Dall%20openid%26data%3D"		
		c = Client(application, BaseResponse)
		resp = c.get(
			'/api/method/frappe.integrations.oauth2.authorize?' +
			'client_id=test_client_id&' +
			'scope=all%20openid&' +
			'response_type=code&' +
			'redirect_uri=http://localhost'
		)
		self.assertTrue(resp.status_code == 302)
		self.assertTrue(expect_in_resp_data in resp.data)
