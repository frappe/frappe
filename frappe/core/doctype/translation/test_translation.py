# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

from frappe import _

class TestTranslation(unittest.TestCase):
	def setUp(self):
		frappe.db.sql('delete from tabTranslation')

	def tearDown(self):
		frappe.local.lang = 'en'
		frappe.local.lang_full_dict=None

	def test_doctype(self):
		translation_data = get_translation_data()
		for key, val in translation_data.items():
			frappe.local.lang = key
			frappe.local.lang_full_dict=None
			translation = create_translation(key, val)
			self.assertEquals(_(val[0]), val[1])

			frappe.delete_doc('Translation', translation.name)
			frappe.local.lang_full_dict=None

			self.assertEquals(_(val[0]), val[0])

	def test_parent_language(self):
		data = [
			['es', ['Test Data', 'datos de prueba']],
			['es', ['Test Spanish', 'prueba de español']],
			['es-MX', ['Test Data', 'pruebas de datos']]
		]

		for key, val in data:
			create_translation(key, val)

		frappe.local.lang = 'es'

		frappe.local.lang_full_dict=None
		self.assertTrue(_(data[0][0]), data[0][1])

		frappe.local.lang_full_dict=None
		self.assertTrue(_(data[1][0]), data[1][1])

		frappe.local.lang = 'es-MX'

		# different translation for es-MX
		frappe.local.lang_full_dict=None
		self.assertTrue(_(data[2][0]), data[2][1])

		# from spanish (general)
		frappe.local.lang_full_dict=None
		self.assertTrue(_(data[1][0]), data[1][1])

def get_translation_data():
	html_source_data = """<font color="#848484" face="arial, tahoma, verdana, sans-serif">
							<span style="font-size: 11px; line-height: 16.9px;">Test Data</span></font>"""
	html_translated_data = """<font color="#848484" face="arial, tahoma, verdana, sans-serif">
							<span style="font-size: 11px; line-height: 16.9px;"> testituloksia </span></font>"""

	return {'hr': ['Test data', 'Testdaten'],
			'ms': ['Test Data','ujian Data'],
			'et': ['Test Data', 'testandmed'],
			'es': ['Test Data', 'datos de prueba'],
			'en': ['Quotation', 'Tax Invoice'],
			'fi': [html_source_data, html_translated_data]}

def create_translation(key, val):
	translation = frappe.new_doc('Translation')
	translation.language = key
	translation.source_name = val[0]
	translation.target_name = val[1]
	translation.save()
	return translation
