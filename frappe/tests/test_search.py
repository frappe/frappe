# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.desk.search import search_link
from frappe.desk.search import search_widget

class TestSearch(unittest.TestCase):
	def test_search_field_sanitizer(self):
		# pass
		search_link('DocType', 'User', query=None, filters=None, page_length=20, searchfield='name')
		result = frappe.response['results'][0]
		self.assertTrue('User' in result['value'])

		#raise exception on injection
		self.assertRaises(frappe.DataError,
			search_link, 'DocType', 'Customer', query=None, filters=None,
			page_length=20, searchfield='1=1')

		self.assertRaises(frappe.DataError,
			search_link, 'DocType', 'Customer', query=None, filters=None,
			page_length=20, searchfield='select * from tabSessions) --')

		self.assertRaises(frappe.DataError,
			search_link, 'DocType', 'Customer', query=None, filters=None,
			page_length=20, searchfield='name or (select * from tabSessions)')

		self.assertRaises(frappe.DataError,
			search_link, 'DocType', 'Customer', query=None, filters=None,
			page_length=20, searchfield='*')

		self.assertRaises(frappe.DataError,
			search_link, 'DocType', 'Customer', query=None, filters=None,
			page_length=20, searchfield=';')

		self.assertRaises(frappe.DataError,
			search_link, 'DocType', 'Customer', query=None, filters=None,
			page_length=20, searchfield=';')

	#Search for the word "pay", part of the word "pays" (country) in french.
	def test_link_search_in_foreign_language(self):
		frappe.local.lang = 'fr'
		search_widget(doctype="DocType", txt="pay", page_length=20)
		output = frappe.response["values"]

		result = [['found' for x in y if x=="Country"] for y in output]
		self.assertTrue(['found'] in result)

	def tearDown(self):
		frappe.local.lang = 'en'

	def test_validate_and_sanitize_search_inputs(self):

		# should raise error if searchfield is injectable
		self.assertRaises(frappe.DataError,
			get_data, *('User', 'Random', 'select * from tabSessions) --', '1', '10', dict()))

		# page_len and start should be converted to int
		self.assertListEqual(get_data('User', 'Random', 'email', 'name or (select * from tabSessions)', '10', dict()),
			['User', 'Random', 'email', 0, 10, {}])
		self.assertListEqual(get_data('User', 'Random', 'email', page_len='2', start='10', filters=dict()),
			['User', 'Random', 'email', 10, 2, {}])

		# DocType can be passed as None which should be accepted
		self.assertListEqual(get_data(None, 'Random', 'email', '2', '10', dict()),
			[None, 'Random', 'email', 2, 10, {}])

		# return empty string if passed doctype is invalid
		self.assertListEqual(get_data("Random DocType", 'Random', 'email', '2', '10', dict()), [])

		# should not fail if function is called via frappe.call with extra arguments
		args = ("Random DocType", 'Random', 'email', '2', '10', dict())
		kwargs = {'as_dict': False}
		self.assertListEqual(frappe.call('frappe.tests.test_search.get_data', *args, **kwargs), [])

@frappe.validate_and_sanitize_search_inputs
def get_data(doctype, txt, searchfield, start, page_len, filters):
	return [doctype, txt, searchfield, start, page_len, filters]