#  -*- coding: utf-8 -*-

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

class TestDB(unittest.TestCase):
	def test_get_value(self):
		self.assertEquals(frappe.db.get_value("User", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"name": ["!=", "Guest"]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"name": ["<", "B"]}), "Administrator")
		self.assertEquals(frappe.db.get_value("User", {"name": ["<=", "Administrator"]}), "Administrator")
		self.assertEquals("test1@example.com", frappe.db.get_value("User", {"name": [">", "s"]}))
		self.assertEquals("test1@example.com", frappe.db.get_value("User", {"name": [">=", "t"]}))

	def test_escape(self):
		frappe.db.escape("香港濟生堂製藥有限公司 - IT".encode("utf-8"))
