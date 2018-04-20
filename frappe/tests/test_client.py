# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

from __future__ import unicode_literals

import unittest, frappe

class TestClient(unittest.TestCase):
	def test_set_value(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='test')).insert()
		frappe.set_value('ToDo', todo.name, 'description', 'test 1')
		self.assertEqual(frappe.get_value('ToDo', todo.name, 'description'), 'test 1')

		frappe.set_value('ToDo', todo.name, {'description': 'test 2'})
		self.assertEqual(frappe.get_value('ToDo', todo.name, 'description'), 'test 2')

	def test_delete(self):
		from frappe.client import delete

		todo = frappe.get_doc(dict(doctype='ToDo', description='description')).insert()
		delete("ToDo", todo.name)

		self.assertFalse(frappe.db.exists("ToDo", todo.name))
		self.assertRaises(frappe.DoesNotExistError, delete, "ToDo", todo.name)
