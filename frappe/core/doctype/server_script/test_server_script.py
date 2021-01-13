# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import requests
from frappe.utils import get_site_url

scripts = [
	dict(
		name='test_todo',
		script_type = 'DocType Event',
		doctype_event = 'Before Insert',
		reference_doctype = 'ToDo',
		script = '''
if "test" in doc.description:
	doc.status = 'Closed'
'''
	),
	dict(
		name='test_todo_validate',
		script_type = 'DocType Event',
		doctype_event = 'Before Insert',
		reference_doctype = 'ToDo',
		script = '''
if "validate" in doc.description:
	raise frappe.ValidationError
'''
	),
	dict(
		name='test_api',
		script_type = 'API',
		api_method = 'test_server_script',
		allow_guest = 1,
		script = '''
frappe.response['message'] = 'hello'
'''
	),
	dict(
		name='test_return_value',
		script_type = 'API',
		api_method = 'test_return_value',
		allow_guest = 1,
		script = '''
frappe.flags = 'hello'
'''
	),
	dict(
		name='test_permission_query',
		script_type = 'Permission Query',
		reference_doctype = 'ToDo',
		script = '''
conditions = '1 = 1'
'''),
  dict(
		name='test_invalid_namespace_method',
		script_type = 'DocType Event',
		doctype_event = 'Before Insert',
		reference_doctype = 'Note',
		script = '''
frappe.method_that_doesnt_exist("do some magic")
'''
	)
]
class TestServerScript(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe.db.commit()
		frappe.db.sql('truncate `tabServer Script`')
		frappe.get_doc('User', 'Administrator').add_roles('Script Manager')
		for script in scripts:
			script_doc = frappe.get_doc(doctype ='Server Script')
			script_doc.update(script)
			script_doc.insert()

		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.commit()
		frappe.db.sql('truncate `tabServer Script`')
		frappe.cache().delete_key('server_script_map')

	def setUp(self):
		frappe.cache().delete_value('server_script_map')

	def test_doctype_event(self):
		todo = frappe.get_doc(dict(doctype='ToDo', description='hello')).insert()
		self.assertEqual(todo.status, 'Open')

		todo = frappe.get_doc(dict(doctype='ToDo', description='test todo')).insert()
		self.assertEqual(todo.status, 'Closed')

		self.assertRaises(frappe.ValidationError, frappe.get_doc(dict(doctype='ToDo', description='validate me')).insert)

	def test_api(self):
		response = requests.post(get_site_url(frappe.local.site) + "/api/method/test_server_script")
		self.assertEqual(response.status_code, 200)
		self.assertEqual("hello", response.json()["message"])

	def test_api_return(self):
		self.assertEqual(frappe.get_doc('Server Script', 'test_return_value').execute_method(), 'hello')

	def test_permission_query(self):
		self.assertTrue('where (1 = 1)' in frappe.db.get_list('ToDo', return_query=1))
		self.assertTrue(isinstance(frappe.db.get_list('ToDo'), list))

	def test_attribute_error(self):
		"""Raise AttributeError if method not found in Namespace"""
		note = frappe.get_doc({"doctype": "Note", "title": "Test Note: Server Script"})
		self.assertRaises(AttributeError, note.insert)
