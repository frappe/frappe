# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import validate_url

# test_records = frappe.get_test_records('Email Group')


class TestEmailGroup(FrappeTestCase):
	def test_welcome_url(self):
		email_group = frappe.new_doc("Email Group")
		email_group.title = "Test"
		email_group.welcome_url = "http://example.com/welcome?hello=world"
		email_group.add_query_parameters = 1
		email_group.insert()

		welcome_url = email_group.get_welcome_url("mail@example.org")
		self.assertTrue(validate_url(welcome_url))
		self.assertIn(email_group.welcome_url, welcome_url)
		self.assertIn("email_group=Test", welcome_url)
		self.assertIn("email=mail%40example.org", welcome_url)

		email_group.add_query_parameters = 0
		welcome_url = email_group.get_welcome_url("mail@example.org")
		self.assertTrue(validate_url(welcome_url))
		self.assertIn(email_group.welcome_url, welcome_url)
		self.assertNotIn("email_group=Test", welcome_url)
		self.assertNotIn("email=mail%40example.org", welcome_url)

		email_group.welcome_url = ""
		self.assertEqual(email_group.get_welcome_url(), None)
