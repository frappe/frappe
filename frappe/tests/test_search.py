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
