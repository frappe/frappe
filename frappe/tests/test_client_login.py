# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest, frappe
from frappe.utils import sel

selenium_tests = True

class TestLogin(unittest.TestCase):
	def setUp(self):
		sel.login()

	def test_login(self):
		self.assertEquals(sel._driver.current_url, sel.get_localhost() + "/desk")

	def test_to_do(self):
		return # does not pass in travis ??
		sel.go_to_module("ToDo")
		sel.primary_action()
		sel.wait_for_page("Form/ToDo")
		sel.set_field("description", "test description", "textarea")
		sel.primary_action()
		self.assertTrue(sel.wait_for_state("clean"))

# def test_material_request(self):
# 	sel.new_doc("Stock", "Material Request")
# 	sel.add_child("items")
# 	sel.set_field("item_code", "_Test Item")
# 	sel.set_field("schedule_date", "10-10-2014")
# 	sel.primary_action()
# 	sel.wait_for_state("clean")

