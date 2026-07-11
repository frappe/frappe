# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase


class TestOAuthClient(IntegrationTestCase):
	def test_generates_strong_client_secret(self):
		client = frappe.new_doc("OAuth Client")

		client.validate()

		self.assertGreaterEqual(len(client.client_secret), 56)
