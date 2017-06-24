# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

from __future__ import unicode_literals

import unittest, frappe

class TestClient(unittest.TestCase):
	def test_set_value(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='test')).insert()
		frappe.set_value('ToDo', todo.name, 'description', 'test 1')
		self.assertEquals(frappe.get_value('ToDo', todo.name, 'description'), 'test 1')

		frappe.set_value('ToDo', todo.name, {'description': 'test 2'})
		self.assertEquals(frappe.get_value('ToDo', todo.name, 'description'), 'test 2')

