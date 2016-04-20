# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import unittest

test_records = frappe.get_test_records('Role')

class TestUser(unittest.TestCase):
	def test_disable_role(self):
		frappe.get_doc("User", "test@example.com").add_roles("_Test Role 3")
		
		role = frappe.get_doc("Role", "_Test Role 3")
		role.disabled = 1
		role.save()
		
		self.assertTrue("_Test Role 3" not in frappe.get_roles("test@example.com"))
		
		frappe.get_doc("User", "test@example.com").add_roles("_Test Role 3")
		self.assertTrue("_Test Role 3" not in frappe.get_roles("test@example.com"))
		
		role = frappe.get_doc("Role", "_Test Role 3")
		role.disabled = 0
		role.save()
		
		frappe.get_doc("User", "test@example.com").add_roles("_Test Role 3")
		self.assertTrue("_Test Role 3" in frappe.get_roles("test@example.com"))
		