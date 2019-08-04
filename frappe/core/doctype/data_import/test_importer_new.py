# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import datetime
import unittest
import frappe
from frappe.core.doctype.data_import.importer_new import Importer

content_empty_rows = '''title,start_date,idx,show_title
,,,
est phasellus sit amet,5/20/2019,52,1
nibh in,7/29/2019,77,1
'''

content_mandatory_missing = '''title,start_date,idx,show_title
,5/20/2019,52,1
'''

content_convert_value = '''title,start_date,idx,show_title
est phasellus sit amet,5/20/2019,52,True
'''

content_invalid_column = '''title,start_date,idx,show_title,invalid_column
est phasellus sit amet,5/20/2019,52,True,invalid value
'''


class TestImporter(unittest.TestCase):
	def test_should_skip_empty_rows(self):
		i = Importer('Web Page', content=content_empty_rows)
		i.import_data()
		self.assertEqual(len(i.skipped_rows), 1)

	def test_should_throw_if_mandatory_is_missing(self):
		i = Importer('Web Page', content=content_mandatory_missing)
		self.assertRaises(frappe.MandatoryError, i.import_data)

	def test_should_convert_value_based_on_fieldtype(self):
		i = Importer('Web Page', content=content_convert_value)
		doc = i.parse_data_for_import(i.data[0], 0)

		self.assertEqual(type(doc.show_title), int)
		self.assertEqual(type(doc.idx), int)
		self.assertEqual(type(doc.start_date), datetime.datetime)

	def test_should_ignore_invalid_columns(self):
		i = Importer('Web Page', content=content_invalid_column)
		doc = i.parse_data_for_import(i.data[0], 0)

		self.assertTrue('invalid_column' not in doc)
		self.assertTrue('title' in doc)
