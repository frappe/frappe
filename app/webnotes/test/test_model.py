"""
Tests for model

TODO:

Model

x insert
x read
x update
* delete
* rename

x validate correct links
x validate correct options
x validate mandatory

Collection

x insert
x read
x update
* delete
* rename

* call methods

* validate before delete
* naming series

* tests with children

* submit
* cancel
* custom fields

* permissions
-----------------
* custom property patch (add fieldname)
* reimplement foreign keys
* methods

"""

import unittest
import webnotes

from webnotes.model.collection import DatabaseCollection
from webnotes.model.model import DatabaseModel

class TestModel(unittest.TestCase):
	def setUp(self):
		webnotes.conn.begin()

	def get_test_model(self):
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
		m = self.get_test_model()
		m.insert()
		m2 = DatabaseModel('Sandbox',m.name)
		self.assertEquals(m2.test_data, 'value')
	
	def test_upate_db_model(self):

		m = self.get_test_model()
		m.insert()

		m2 = DatabaseModel('Sandbox',m.name)
		m2.test_data = 'new_value'
		m2.update()
		
		self.assertTrue(webnotes.conn.get_value('Sandbox',m.name,'test_data')=='new_value')
				

	def test_read_file_collection(self):
		from webnotes.model.collection import FileCollection
		f = FileCollection('Core', 'DocType', 'Sandbox')
		self.assertTrue(f.parent.name=='Sandbox')
		
	def test_insert_db_collection(self):
		dc = DatabaseCollection('Sandbox', models=[self.get_test_model()])
		dc.insert()
		
		dc2 = DatabaseCollection('Sandbox', dc.parent.name)
		self.assertEquals(dc2.parent.test_data, 'value')
		
	def test_update_db_collection(self):

		dc = DatabaseCollection('Sandbox', models=[self.get_test_model()])
		dc.insert()
		
		dc2 = DatabaseCollection('Sandbox', dc.parent.name)
		dc2.parent.test_data = 'new_value'
		dc2.update()
		
		self.assertTrue(webnotes.conn.get_value('Sandbox', dc.parent.name, 'test_data')=='new_value')
		
	def test_validate_bad_link(self):
		dc = DatabaseCollection('Sandbox', models=[self.get_test_model()])
		dc.parent.test_link = 'xxx'
		self.assertRaises(webnotes.InvalidLinkError, dc.insert)

	def test_validate_bad_options(self):
		dc = DatabaseCollection('Sandbox', models=[self.get_test_model()])
		dc.parent.test_select = 'xxx'
		self.assertRaises(webnotes.InvalidOptionError, dc.insert)

	def test_validate_mandatory(self):
		dc = DatabaseCollection('Sandbox', models=[self.get_test_model()])
		dc.parent.load_def()
		# make mandatory
		dc.parent.get_properties(fieldname='test_data')[0].reqd = 1
		dc.parent.test_data = None
		self.assertRaises(webnotes.MandatoryAttributeError, dc.insert)
		
	def tearDown(self):
		webnotes.conn.rollback()
		