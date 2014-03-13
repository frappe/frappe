# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.test_runner import make_test_records
from frappe.core.doctype.user.user import STANDARD_USERS

class TestDB(unittest.TestCase):
	def test_get_value(self):
		from frappe.utils import now_datetime
		import time
		frappe.db.sql("""delete from `tabUser` where name not in ({})""".format(", ".join(["%s"]*len(STANDARD_USERS))), 
			STANDARD_USERS)
		
		now = now_datetime()
		
		self.assertEquals(frappe.db.get_value("User", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"name": ["!=", "Guest"]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"modified": ["<", now]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"modified": ["<=", now]}), "Administrator")

		time.sleep(2)
		if "User" in frappe.local.test_objects:
			del frappe.local.test_objects["User"]
		make_test_records("User")
		
		self.assertEquals("test1@example.com", frappe.db.get_value("User", {"modified": [">", now]}))
		self.assertEquals("test1@example.com", frappe.db.get_value("User", {"modified": [">=", now]}))
		