# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestActionSetValue(unittest.TestCase):
	def test_static_value(self):
		action_set_value = frappe.get_doc(dict(
			doctype = 'Action Set Value',
			enabled = 1,
			document_type = 'ToDo',
			event = 'Save',
			condition = 'doc.description == "Test Trigger"',
			fieldname = 'status',
			value = 'Closed'
		)).insert()

		todo = frappe.get_doc(dict(
			doctype = 'ToDo',
			description = 'something'
		)).insert()

		self.assertEquals(todo.status, 'Open')

		todo.reload()
		todo.description = 'something else'
		todo.save()

		self.assertEquals(todo.status, 'Open')

		todo.reload()
		todo.description = 'Test Trigger'
		todo.save()

		self.assertEquals(todo.status, 'Closed')