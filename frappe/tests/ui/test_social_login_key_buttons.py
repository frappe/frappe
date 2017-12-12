# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe, requests, time
from frappe.test_runner import make_test_records
from frappe.utils.selenium_testdriver import TestDriver
from six.moves.urllib.parse import urlparse, parse_qs

class TestSocialLoginKeyButtons(unittest.TestCase):
	def setUp(self):
		try:
			frappe_login_key = frappe.get_doc("Social Login Key", "frappe")
		except:
			frappe_login_key = frappe.new_doc("Social Login Key")
		frappe_login_key.get_social_login_provider("Frappe", initialize=True)
		frappe_login_key.base_url = "http://localhost:8000"
		frappe_login_key.save()
		frappe.db.commit()

		self.driver = TestDriver()

	def test_login_buttons(self):

		# Go to Login Page
		self.driver.get("login")

		time.sleep(2)
		frappe_social_login = self.driver.find(".btn-frappe")
		self.assertTrue(len(frappe_social_login) > 0)

	def tearDown(self):
		self.driver.close()