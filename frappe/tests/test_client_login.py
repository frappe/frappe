# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import unittest, frappe
from frappe.utils import sel

class TestLogin(unittest.TestCase):
	def setUp(self):
		sel.start()

	def test_login(self):
		sel.driver.get(frappe.local.localhost + "/login")
		sel.wait("#login_email")
		elem = sel.find("#login_email")[0]
		elem.send_keys("Administrator")
		elem = sel.find("#login_password")[0]
		elem.send_keys("admin", sel.Keys.RETURN)
		sel.wait("#body_div")
		self.assertEquals(sel.driver.current_url, frappe.local.localhost + "/desk")

	def tearDown(self):
		sel.driver.close()
