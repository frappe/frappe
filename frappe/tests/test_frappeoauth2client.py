# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe, requests, time
from frappe.test_runner import make_test_records
from frappe.utils.selenium_testdriver import TestDriver
from six.moves.urllib.parse import urlparse
from frappe.frappeclient import FrappeOAuth2Client

class TestFrappeOAuth2Client(unittest.TestCase):
	def setUp(self):
		self.driver = TestDriver()
		make_test_records("OAuth Client")
		make_test_records("User")
		self.client_id = frappe.get_all("OAuth Client", fields=["*"])[0].get("client_id")

		# Set Frappe server URL reqired for id_token generation
		frappe.db.set_value("Social Login Keys", None, "frappe_server_url", "http://localhost:8000")
		frappe.db.commit()

	def test_insert_note(self):

		# Go to Authorize url
		self.driver.get(
			"api/method/frappe.integrations.oauth2.authorize?client_id=" +
			self.client_id +
			"&scope=all%20openid&response_type=code&redirect_uri=http%3A%2F%2Flocalhost"
		)

		time.sleep(2)

		# Login
		username = self.driver.find("#login_email")[0]
		username.send_keys("test@example.com")

		password = self.driver.find("#login_password")[0]
		password.send_keys("Eastern_43A1W")

		sign_in = self.driver.find(".btn-login")[0]
		sign_in.submit()

		time.sleep(2)

		# Allow access to resource
		allow = self.driver.find("#allow")[0]
		allow.click()

		time.sleep(2)

		# Get authorization code from redirected URL
		auth_code = urlparse(self.driver.driver.current_url).query.split("=")[1]

		payload = "grant_type=authorization_code&code="
		payload += auth_code
		payload += "&redirect_uri=http%3A%2F%2Flocalhost&client_id="
		payload += self.client_id

		headers = {'content-type':'application/x-www-form-urlencoded'}

		# Request for bearer token
		token_response = requests.post( frappe.get_site_config().host_name +
			"/api/method/frappe.integrations.oauth2.get_token", data=payload, headers=headers)

		# Parse bearer token json
		bearer_token = token_response.json()
		client = FrappeOAuth2Client(frappe.get_site_config().host_name, bearer_token.get("access_token"))

		notes = [
			{"doctype": "Note", "title": "Sing", "public": True},
			{"doctype": "Note", "title": "a", "public": True},
			{"doctype": "Note", "title": "Song", "public": True},
			{"doctype": "Note", "title": "of", "public": True},
			{"doctype": "Note", "title": "sixpence", "public": True}
		]

		for note in notes:
			client.insert(note)

		self.assertTrue(len(frappe.get_all("Note")) == 5)
