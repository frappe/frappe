# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

from frappe.model.naming import append_number_if_name_exists

class TestNaming(unittest.TestCase):
	def test_append_number_if_name_exists(self):
		'''
		Append number to name based on existing values
		if Bottle exists
			Bottle -> Bottle-1
		if Bottle-1 exists
			Bottle -> Bottle-2
		'''

		note = frappe.new_doc('Note')
		note.title = 'Test'
		note.insert()

		title2 = append_number_if_name_exists('Note', 'Test')
		self.assertEquals(title2, 'Test-1')

		title2 = append_number_if_name_exists('Note', 'Test', 'title', '_')
		self.assertEquals(title2, 'Test_1')
