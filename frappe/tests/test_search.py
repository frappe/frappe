# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.desk.search import search_link
from frappe.contacts.address_and_contact import filter_dynamic_link_doctypes
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
	
	#First search for the word "cust" and get "Customer" as result.
	#Then search for the word "clie", part of the word "client" (customer) in french.
	def test_contact_search_in_foreign_language(self):
		frappe.local.lang = 'en'
		output = filter_dynamic_link_doctypes("DocType", "cust", "name", 0, 30, {'fieldtype': 'HTML', 'fieldname': 'contact_html'})

		result = [['found' for x in y if x=="Customer"] for y in output]
		self.assertTrue(['found'] in result)

		frappe.local.lang = 'fr'
		output = filter_dynamic_link_doctypes("DocType", "clie", "name", 0, 30, {'fieldtype': 'HTML', 'fieldname': 'contact_html'})

		result = [['found' for x in y if x=="Customer"] for y in output]
		self.assertTrue(['found'] in result)

	#First search for the word "suppl" and get "Supplier" as result.
	#Then search for the word "fourn", part of the word "fournisseur" (supplier) in french.
	def test_link_search_in_foreign_language(self):
		frappe.local.lang = 'en'
		search_widget(doctype="DocType", txt="suppl", page_length=30)
		output = frappe.response["values"]
		print(output)

		result = [['found' for x in y if x=="Supplier"] for y in output]
		self.assertTrue(['found'] in result)

		frappe.local.lang = 'fr'
		search_widget(doctype="DocType", txt="fourn", page_length=30)
		output = frappe.response["values"]
		print(output)

		result = [['found' for x in y if x=="Supplier"] for y in output]
		self.assertTrue(['found'] in result)

	def tearDown(self):
		frappe.local.lang = 'en'
