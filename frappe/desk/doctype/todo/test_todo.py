# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

# test_records = frappe.get_test_records('ToDo')

class TestToDo(unittest.TestCase):
	def test_fetch(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='test todo',
			assigned_by='Administrator')).insert()
		self.assertEquals(todo.assigned_by_full_name,
			frappe.db.get_value('User', todo.assigned_by, 'full_name'))
