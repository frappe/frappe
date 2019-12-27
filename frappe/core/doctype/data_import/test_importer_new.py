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
		i = self.get_importer('Web Page', content=content_empty_rows)
		payloads = i.get_payloads_for_import()
		row_to_be_imported = []
		for p in payloads:
			row_to_be_imported += [row[0] for row in p.rows]
		self.assertEqual(len(row_to_be_imported), 2)

	def test_should_throw_if_mandatory_is_missing(self):
		i = self.get_importer('Web Page', content=content_mandatory_missing)
		i.import_data()
		warning = i.warnings[0]
		self.assertTrue('Title is a mandatory field' in warning['message'])

	def test_should_convert_value_based_on_fieldtype(self):
		i = self.get_importer('Web Page', content=content_convert_value)
		payloads = i.get_payloads_for_import()
		doc = payloads[0].doc

		self.assertEqual(type(doc['show_title']), int)
		self.assertEqual(type(doc['idx']), int)
		self.assertEqual(type(doc['start_date']), datetime.datetime)

	def test_should_ignore_invalid_columns(self):
		i = self.get_importer('Web Page', content=content_invalid_column)
		payloads = i.get_payloads_for_import()
		doc = payloads[0].doc

		self.assertTrue('invalid_column' not in doc)
		self.assertTrue('title' in doc)

	def test_should_import_valid_template(self):
		title = 'est phasellus sit amet {0}'.format(frappe.utils.random_string(8))
		content_valid_content = '''title,start_date,idx,show_title
{0},5/20/2019,52,1'''.format(title)
		i = self.get_importer('Web Page', content=content_valid_content)
		import_log = i.import_data()
		log = import_log[0]
		self.assertTrue(log.success)
		doc = frappe.get_doc('Web Page', { 'title': title })
		self.assertEqual(frappe.utils.get_datetime_str(doc.start_date),
			frappe.utils.get_datetime_str('2019-05-20'))

	def get_importer(self, doctype, content):
		data_import = frappe.new_doc('Data Import Beta')
		data_import.import_type = 'Insert New Records'
		i = Importer(doctype, content=content, data_import=data_import)
		return i
