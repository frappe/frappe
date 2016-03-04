# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

from frappe import _

class TestTranslation(unittest.TestCase):
	def tearDown(self):
		frappe.local.lang = 'en'
		frappe.local.lang_full_dict=None

	def test_doctype(self):
		translation_data = get_translation_data()
		for key, val in translation_data.items():
			frappe.local.lang = key
			frappe.local.lang_full_dict=None
			translation = create_translation(key, val)
			self.assertEquals(_(translation.source_name), val[1])

			frappe.delete_doc('Translation', translation.name)
			frappe.local.lang_full_dict=None
			self.assertEquals(_(translation.source_name), val[0])

def get_translation_data():
	html_source_data = """ <font color="#848484" face="arial, tahoma, verdana, sans-serif">
							<span style="font-size: 11px; line-height: 16.9px;">Test Data</span></font> """
	html_translated_data = """ <font color="#848484" face="arial, tahoma, verdana, sans-serif">
							<span style="font-size: 11px; line-height: 16.9px;"> testituloksia </span></font>"""

	return {'hr': ['Test data', 'Testdaten'],
			'ms': ['Test Data','ujian Data'],
			'et': ['Test Data', 'testandmed'],
			'en': ['Quotation', 'Tax Invoice'],
			'fi': [html_source_data, html_translated_data]}

def create_translation(key, val):
	translation = frappe.new_doc('Translation')
	translation.language_code = key
	translation.source_name = val[0]
	translation.target_name = val[1]
	translation.save()
	return translation
