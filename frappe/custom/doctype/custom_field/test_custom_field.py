#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import frappe
import unittest

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

class TestCustomField(unittest.TestCase):
	def test_custom_field_sorting(self):
		custom_fields = {
			'ToDo': [
				{
					'fieldname': 'test_field_0',
					'fieldtype': 'Data',
					'insert_after': 'description'
				},
				{
					'fieldname': 'test_field_1',
					'fieldtype': 'Data',
					'insert_after': 'not_a_real_reference'
				}
			]
		}

		create_custom_fields(custom_fields, ignore_validate=True)
		meta = frappe.get_meta('ToDo')

		for i, df in enumerate(meta.fields):
			if df.fieldname == 'test_field_0':
				self.assertEqual(meta.fields[i - 1].fieldname, 'description')
				break

		self.assertEqual(meta.fields[-1].fieldname, 'test_field_1')
