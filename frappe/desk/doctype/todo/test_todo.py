# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.model.db_query import DatabaseQuery
from frappe.permissions import get_doc_permissions

# test_records = frappe.get_test_records('ToDo')
test_user_records = frappe.get_test_records('User')

class TestToDo(unittest.TestCase):
	def test_delete(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='test todo',
			assigned_by='Administrator')).insert()

		frappe.db.sql('delete from `tabDeleted Document`')
		todo.delete()

		deleted = frappe.get_doc('Deleted Document', dict(deleted_doctype=todo.doctype, deleted_name=todo.name))
		self.assertEqual(todo.as_json(), deleted.data)

	def test_fetch(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='test todo',
			assigned_by='Administrator')).insert()
		self.assertEqual(todo.assigned_by_full_name,
			frappe.db.get_value('User', todo.assigned_by, 'full_name'))

	def test_fetch_setup(self):
		frappe.db.sql('delete from tabToDo')

		todo_meta = frappe.get_doc('DocType', 'ToDo')
		todo_meta.get('fields', dict(fieldname='assigned_by_full_name'))[0].fetch_from = ''
		todo_meta.save()

		frappe.clear_cache(doctype='ToDo')

		todo = frappe.get_doc(dict(doctype='ToDo', description='test todo',
			assigned_by='Administrator')).insert()
		self.assertFalse(todo.assigned_by_full_name)

		todo_meta = frappe.get_doc('DocType', 'ToDo')
		todo_meta.get('fields', dict(fieldname='assigned_by_full_name'))[0].fetch_from = 'assigned_by.full_name'
		todo_meta.save()

		todo.reload()

		self.assertEqual(todo.assigned_by_full_name,
			frappe.db.get_value('User', todo.assigned_by, 'full_name'))

	def test_access(self):
		todo1 = create_new_todo('Test1', 'Administrator')
		todo2 = create_new_todo('Test2', 'test4@example.com')

		frappe.set_user('test4@example.com')
		test_user_data = DatabaseQuery('ToDo').execute()

		self.assertFalse(todo1.has_permission("read"))
		self.assertFalse(todo1.has_permission("write"))
		self.assertTrue(todo2.has_permission("read"))
		self.assertTrue(todo2.has_permission("write"))

		frappe.set_user('Administrator')
		admin_data = DatabaseQuery('ToDo').execute()

		self.assertTrue(todo1.has_permission("read"))
		self.assertTrue(todo1.has_permission("write"))
		self.assertTrue(todo2.has_permission("read"))
		self.assertTrue(todo2.has_permission("write"))

		self.assertNotEqual(test_user_data, admin_data)

		frappe.db.rollback()

	def test_doc_read_access(self):
		todo1 = create_new_todo('Test1', 'Administrator')
		todo2 = create_new_todo('Test2', 'test4@example.com')

		# user without role permission to read ToDo's
		frappe.set_user('test4@example.com')
		user_todo1_permission = get_doc_permissions(todo1)
		user_todo2_permission = get_doc_permissions(todo2)
		self.assertFalse(user_todo1_permission.get("read"))
		self.assertTrue(user_todo2_permission.get("read"))

		# user with role permission to read ToDo's
		frappe.set_user('test@example.com')
		user_todo1_permission = get_doc_permissions(todo1)
		user_todo2_permission = get_doc_permissions(todo2)
		self.assertTrue(user_todo1_permission.get("read"))
		self.assertTrue(user_todo2_permission.get("read"))

		frappe.set_user('Administrator')
		admin_todo1_permission = get_doc_permissions(todo1)
		admin_todo2_permission = get_doc_permissions(todo2)
		self.assertTrue(admin_todo1_permission.get("read"))
		self.assertTrue(admin_todo2_permission.get("read"))

def test_fetch_if_empty(self):
		frappe.db.sql('delete from tabToDo')

		# Allow user changes
		todo_meta = frappe.get_doc('DocType', 'ToDo')
		field = todo_meta.get('fields', dict(fieldname='assigned_by_full_name'))[0]
		field.fetch_from = 'assigned_by.full_name'
		field.fetch_if_empty = 1
		todo_meta.save()

		frappe.clear_cache(doctype='ToDo')

		todo = frappe.get_doc(dict(doctype='ToDo', description='test todo',
			assigned_by='Administrator', assigned_by_full_name='Admin')).insert()

		self.assertEqual(todo.assigned_by_full_name, 'Admin')

		# Overwrite user changes
		todo_meta = frappe.get_doc('DocType', 'ToDo')
		todo_meta.get('fields', dict(fieldname='assigned_by_full_name'))[0].fetch_if_empty = 0
		todo_meta.save()

		todo.reload()
		todo.save()

		self.assertEqual(todo.assigned_by_full_name,
			frappe.db.get_value('User', todo.assigned_by, 'full_name'))

def create_new_todo(description, assigned_by):
	todo = {
		'doctype': 'ToDo',
		'description': description,
		'assigned_by': assigned_by
	}
	return frappe.get_doc(todo).insert()
