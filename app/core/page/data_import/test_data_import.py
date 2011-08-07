"""
Tests for data import.

TODO

- test for overwrite
- test for update
"""

import unittest
import webnotes
from core.page.data_import.data_import import ImportCSV

class TestDataImport(unittest.TestCase):
	def setUp(self):
		webnotes.conn.begin()

	def test_extract_columns(self):
		"extract columns"
		csv = ImportCSV(test_csv)
		self.assertEquals(csv.get_columns(), ['C1', 'C2', 'C3'])
		
	def test_links(self):
		"validate links"
		csv = ImportCSV(test_csv_link, 'Sandbox', test_map)
		self.assertRaises(webnotes.LinkValidationError, csv.imp)

	def test_options(self):
		"validate options"
		csv = ImportCSV(test_csv_options, test_map)
		self.assertRaises(csv.imp(), webnotes.OptionsError)
		
	def test_mandatory(self):
		"validate mandatory"
		csv = ImportCSV(test_csv_reqd, test_map)
		self.assertRaises(csv.imp(), webnotes.MandatoryError)
	
	def test_date_fields(self):
		"check if date fields are interpreted correctly"
		csv = ImportCSV(test_csv_date, test_map)
		csv.imp()
		self.assertEquals(csv.data[0].test_date, '2011-01-22')
	
	def test_with_custom_fields(self):
		"test if custom validations are done"
		csv = ImportCSV(test_csv_custom, test_map)
		self.assertRaises(csv.imp(), webnotes.OptionsError)
		
	def test_success(self):
		"test if the data is imported"
		csv = ImportCSV(test_csv, test_map)
		d1 = Document('Sandbox','test1')
		d2 = Document('Sandobx','test2')
		self.assertTrue(d1.test_data=='A' and d1.test_date=='2011-01-22' and d1.test_link=='Administrator')
		self.assertTrue(d1.test_data=='B' and d1.test_date=='2011-01-23' and d2.test_link=='Guest')
		
	def tearDown(self):
		webnotes.conn.rollback()

test_map = [
	'Test Data',
	'Test Date',
	'Test Link',
	'Test Select'
]

test_csv = '''C1,C2,C3,C4
T1,2011-01-22,'Administrator','A'
T2,2011-01-23,'Guest','B'
'''

test_csv_link = '''C1,C2,C3,C4
T1,2011-01-22,'Administrator','A'
T2,2011-01-23,'xxx','B'
'''

test_csv_option = '''C1,C2,C3,C4
T1,2011-01-22,'Administrator','A'
T2,2011-01-23,'Guest','X'
'''

