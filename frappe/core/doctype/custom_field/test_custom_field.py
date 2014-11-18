#  -*- coding: utf-8 -*-

# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import frappe
import unittest

test_records = frappe.get_test_records('Custom Field')

from frappe.model.db_schema import InvalidColumnName

class TestCustomField(unittest.TestCase):
	def test_non_ascii(self):
		cf = frappe.get_doc({
			"doctype":"Custom Field",
			"dt": "ToDo",
			"fieldtype": "Data",
			"fieldname": "δου"
		})

		self.assertRaises(InvalidColumnName, cf.insert)

		# todo = frappe.get_doc({
		# 	"doctype": "ToDo",
		# 	"description": "test",
		# 	"δου": "greek"
		# })
		# todo.insert()
