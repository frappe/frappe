"""
Tests for model

TODO:

* insert
* read
* update
* delete
* rename

* validate correct links
* validate correct options
* validate mandatory

* validate before delete
* naming series

* custom property patch

"""

import unittest
import webnotes

class TestModel(unittest.TestCase):
	def setUp(self):
		webnotes.conn.begin()

	def get_test_model(self):
		from webnotes.model.model import DatabaseModel
		m = DatabaseModel('Sandbox', attributes = {
			'name': 'SB000x',
			'test_data': 'value',
			'test_date': '2011-01-22',
			'test_select': 'A',
			'garbage': 'x'
		})
		return m
		
	def test_insert_db(self):
		"""
			test model insertion
		"""
		from webnotes.model.model import DatabaseModel
		m = self.get_test_model()
		m.insert()
		m2 = DatabaseModel('Sandbox',m.name)
		m2.read()
		self.assertEquals(m2.test_data, 'value')
	
	def test_read_db_model(self):
		from webnotes.model.model import DatabaseModel
		m = DatabaseModel('DocType', 'Sandbox')
		m.read()
		self.assertTrue(m.name=='Sandbox')

	def test_read_file_collection(self):
		from webnotes.model.collection import FileCollection
		f = FileCollection('Core', 'DocType', 'Sandbox')
		f.read()
		self.assertTrue(f.parent.name=='Sandbox')
		
	def test_insert_db_collection(self):
		from webnotes.model.collection import DatabaseCollection
		from webnotes.model.model import DatabaseModel

		dc = DatabaseCollection('Sanbox', None, models=[self.get_test_model()])
		dc.insert()
		
		dc2 = DatabaseCollection('Sandbox', dc.parent.name)
		dc2.read()
		self.assertEquals(dc2.parent.test_data, 'value')
		
		
		
	def tearDown(self):
		webnotes.conn.rollback()
		