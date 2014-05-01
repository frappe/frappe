# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import unittest, frappe
from frappe.utils import sel

class TestLogin(unittest.TestCase):
	def setUp(self):
		sel.login(frappe.local.localhost)

	def test_login(self):
		self.assertEquals(sel.driver.current_url, frappe.local.localhost + "/desk")

	def test_to_do(self):
		sel.module("ToDo")
		sel.find('.appframe-iconbar .icon-plus')[0].click()
		sel.wait_for_page("Form/ToDo")
		sel.set_field_input("description", "test description")
		sel.primary_action()
		sel.wait_for_state("clean")
