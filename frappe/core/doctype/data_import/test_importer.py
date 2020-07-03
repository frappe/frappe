# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest
import frappe
from frappe.utils import getdate

doctype_name = 'DocType for Import'

class TestImporter(unittest.TestCase):
	def setUp(self):
		create_doctype_if_not_exists(doctype_name)

	def test_data_import_from_file(self):
		import_file = get_import_file('sample_import_file')
		data_import = self.get_importer(doctype_name, import_file)
		data_import.start_import()

		doc1 = frappe.get_doc(doctype_name, 'Test')
		doc2 = frappe.get_doc(doctype_name, 'Test 2')
		doc3 = frappe.get_doc(doctype_name, 'Test 3')

		self.assertEqual(doc1.description, 'test description')
		self.assertEqual(doc1.number, 1)

		self.assertEqual(doc1.table_field_1[0].child_title, 'child title')
		self.assertEqual(doc1.table_field_1[0].child_description, 'child description')

		self.assertEqual(doc1.table_field_1[1].child_title, 'child title 2')
		self.assertEqual(doc1.table_field_1[1].child_description, 'child description 2')

		self.assertEqual(doc1.table_field_2[1].child_2_title, 'title child')
		self.assertEqual(doc1.table_field_2[1].child_2_date, getdate('2019-10-30'))
		self.assertEqual(doc1.table_field_2[1].child_2_another_number, 5)

		self.assertEqual(doc1.table_field_1_again[0].child_title, 'child title again')
		self.assertEqual(doc1.table_field_1_again[1].child_title, 'child title again 2')
		self.assertEqual(doc1.table_field_1_again[1].child_date, getdate('2021-09-22'))

		self.assertEqual(doc2.description, 'test description 2')
		self.assertEqual(doc3.another_number, 5)

	def test_data_import_preview(self):
		import_file = get_import_file('sample_import_file')
		data_import = self.get_importer(doctype_name, import_file)
		preview = data_import.get_preview_from_template()

		self.assertEqual(len(preview.data), 4)
		self.assertEqual(len(preview.columns), 15)

	def test_data_import_without_mandatory_values(self):
		import_file = get_import_file('sample_import_file_without_mandatory')
		data_import = self.get_importer(doctype_name, import_file)
		data_import.start_import()
		data_import.reload()
		warnings = frappe.parse_json(data_import.template_warnings)

		self.assertEqual(warnings[0]['row'], 2)
		self.assertEqual(warnings[0]['message'], "<b>Child Title (Table Field 1)</b> is a mandatory field")

		self.assertEqual(warnings[1]['row'], 3)
		self.assertEqual(warnings[1]['message'], "<b>Child Title (Table Field 1 Again)</b> is a mandatory field")

		self.assertEqual(warnings[2]['row'], 4)
		self.assertEqual(warnings[2]['message'], "<b>Title</b> is a mandatory field")

	def test_data_import_update(self):
		if not frappe.db.exists(doctype_name, 'Test 26'):
			frappe.get_doc(
				doctype=doctype_name,
				title='Test 26'
			).insert()

		import_file = get_import_file('sample_import_file_for_update')
		data_import = self.get_importer(doctype_name, import_file, update=True)
		data_import.start_import()

		updated_doc = frappe.get_doc(doctype_name, 'Test 26')
		self.assertEqual(updated_doc.description, 'test description')
		self.assertEqual(updated_doc.table_field_1[0].child_title, 'child title')
		self.assertEqual(updated_doc.table_field_1[0].child_description, 'child description')
		self.assertEqual(updated_doc.table_field_1_again[0].child_title, 'child title again')

	def get_importer(self, doctype, import_file, update=False):
		data_import = frappe.new_doc('Data Import')
		data_import.import_type = 'Insert New Records' if not update else 'Update Existing Records'
		data_import.reference_doctype = doctype
		data_import.import_file = import_file.file_url
		data_import.insert()

		return data_import

def create_doctype_if_not_exists(doctype_name, force=False):
	if force:
		frappe.delete_doc_if_exists('DocType', doctype_name)
		frappe.delete_doc_if_exists('DocType', 'Child 1 of ' + doctype_name)
		frappe.delete_doc_if_exists('DocType', 'Child 2 of ' + doctype_name)

	if frappe.db.exists('DocType', doctype_name):
		return

	# Child Table 1
	table_1_name = 'Child 1 of ' + doctype_name
	frappe.get_doc({
		'doctype': 'DocType',
		'name': table_1_name,
		'module': 'Custom',
		'custom': 1,
		'istable': 1,
		'fields': [
			{'label': 'Child Title', 'fieldname': 'child_title', 'reqd': 1, 'fieldtype': 'Data'},
			{'label': 'Child Description', 'fieldname': 'child_description', 'fieldtype': 'Small Text'},
			{'label': 'Child Date', 'fieldname': 'child_date', 'fieldtype': 'Date'},
			{'label': 'Child Number', 'fieldname': 'child_number', 'fieldtype': 'Int'},
			{'label': 'Child Number', 'fieldname': 'child_another_number', 'fieldtype': 'Int'},
		]
	}).insert()

	# Child Table 2
	table_2_name = 'Child 2 of ' + doctype_name
	frappe.get_doc({
		'doctype': 'DocType',
		'name': table_2_name,
		'module': 'Custom',
		'custom': 1,
		'istable': 1,
		'fields': [
			{'label': 'Child 2 Title', 'fieldname': 'child_2_title', 'reqd': 1, 'fieldtype': 'Data'},
			{'label': 'Child 2 Description', 'fieldname': 'child_2_description', 'fieldtype': 'Small Text'},
			{'label': 'Child 2 Date', 'fieldname': 'child_2_date', 'fieldtype': 'Date'},
			{'label': 'Child 2 Number', 'fieldname': 'child_2_number', 'fieldtype': 'Int'},
			{'label': 'Child 2 Number', 'fieldname': 'child_2_another_number', 'fieldtype': 'Int'},
		]
	}).insert()

	# Main Table
	frappe.get_doc({
		'doctype': 'DocType',
		'name': doctype_name,
		'module': 'Custom',
		'custom': 1,
		'autoname': 'field:title',
		'fields': [
			{'label': 'Title', 'fieldname': 'title', 'reqd': 1, 'fieldtype': 'Data'},
			{'label': 'Description', 'fieldname': 'description', 'fieldtype': 'Small Text'},
			{'label': 'Date', 'fieldname': 'date', 'fieldtype': 'Date'},
			{'label': 'Number', 'fieldname': 'number', 'fieldtype': 'Int'},
			{'label': 'Number', 'fieldname': 'another_number', 'fieldtype': 'Int'},
			{'label': 'Table Field 1', 'fieldname': 'table_field_1', 'fieldtype': 'Table', 'options': table_1_name},
			{'label': 'Table Field 2', 'fieldname': 'table_field_2', 'fieldtype': 'Table', 'options': table_2_name},
			{'label': 'Table Field 1 Again', 'fieldname': 'table_field_1_again', 'fieldtype': 'Table', 'options': table_1_name},
		],
		'permissions': [
			{'role': 'System Manager'}
		]
	}).insert()


def get_import_file(csv_file_name, force=False):
	file_name = csv_file_name + '.csv'
	_file = frappe.db.exists('File', {'file_name': file_name})
	if force and _file:
		frappe.delete_doc_if_exists('File', _file)

	if frappe.db.exists('File', {'file_name': file_name}):
		f = frappe.get_doc('File', {'file_name': file_name})
	else:
		full_path = get_csv_file_path(file_name)
		f = frappe.get_doc(
			doctype='File',
			content=frappe.read_file(full_path),
			file_name=file_name,
			is_private=1
		)
		f.save(ignore_permissions=True)

	return f


def get_csv_file_path(file_name):
	return frappe.get_app_path('frappe', 'core', 'doctype', 'data_import', 'fixtures', file_name)
