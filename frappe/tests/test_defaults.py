# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest

from frappe.defaults import *

class TestDefaults(unittest.TestCase):
	def test_global(self):
		clear_user_default("key1")
		set_global_default("key1", "value1")
		self.assertEquals(get_global_default("key1"), "value1")

		set_global_default("key1", "value2")
		self.assertEquals(get_global_default("key1"), "value2")

		add_global_default("key1", "value3")
		self.assertEquals(get_global_default("key1"), "value2")
		self.assertEquals(get_defaults()["key1"], ["value2", "value3"])
		self.assertEquals(get_user_default_as_list("key1"), ["value2", "value3"])

	def test_user(self):
		set_user_default("key1", "2value1")
		self.assertEquals(get_user_default_as_list("key1"), ["2value1"])

		set_user_default("key1", "2value2")
		self.assertEquals(get_user_default("key1"), "2value2")

		add_user_default("key1", "3value3")
		self.assertEquals(get_user_default("key1"), "2value2")
		self.assertEquals(get_user_default_as_list("key1"), ["2value2", "3value3"])

	def test_global_if_not_user(self):
		set_global_default("key4", "value4")
		self.assertEquals(get_user_default("key4"), "value4")

	def test_clear(self):
		set_user_default("key5", "value5")
		self.assertEquals(get_user_default("key5"), "value5")
		clear_user_default("key5")
		self.assertEquals(get_user_default("key5"), None)

	def test_clear_global(self):
		set_global_default("key6", "value6")
		self.assertEquals(get_user_default("key6"), "value6")

		clear_default("key6", value="value6")
		self.assertEquals(get_user_default("key6"), None)
