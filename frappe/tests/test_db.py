# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.test_runner import make_test_records

class TestDB(unittest.TestCase):
	def test_get_value(self):
		from frappe.utils import now_datetime
		import time
		frappe.conn.sql("""delete from `tabProfile` where name not in ('Administrator', 'Guest')""")
		
		now = now_datetime()
		
		self.assertEquals(frappe.conn.get_value("Profile", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEquals(frappe.conn.get_value("Profile", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertEquals(frappe.conn.get_value("Profile", {"name": ["!=", "Guest"]}), "Administrator")
		self.assertEquals(frappe.conn.get_value("Profile", {"modified": ["<", now]}), "Administrator")
		self.assertEquals(frappe.conn.get_value("Profile", {"modified": ["<=", now]}), "Administrator")

		time.sleep(2)
		if "Profile" in frappe.local.test_objects:
			del frappe.local.test_objects["Profile"]
		make_test_records("Profile")
		
		self.assertEquals("test1@example.com", frappe.conn.get_value("Profile", {"modified": [">", now]}))
		self.assertEquals("test1@example.com", frappe.conn.get_value("Profile", {"modified": [">=", now]}))
		