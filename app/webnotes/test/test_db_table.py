"""
Tests for database creation, schemas etc
"""

from webnotes.model.collection import Collection
from webnotes.model.model import DatabaseModel
from webnotes.db.row import DatabaseRow

from webnotes.run_tests import TestCase
from webnotes.db.errors import *

test_model_def = Collection(raw_models = [
		{
			'name': 'Temp Sandbox',
			'doctype': 'DocType'
		},
		{
			'doctype':'DocField',
			'fieldname':'test_data',
			'label':'Test Data',
			'fieldtype':'Data'
		},
		{
			'doctype':'DocField',
			'fieldname':'test_link',
			'label':'Test Link',
			'fieldtype':'Link',
			'options': 'Profile'
		}
	]
)

test_model = DatabaseModel(attributes = {
	'doctype': 'Temp Sandbox',
	'test_data': 'test',
	'test_link': 'Guest'
})

from webnotes.db.table import DatabaseTable

class TestDbTable(TestCase):
	def setUp(self):
		pass
		
	def test_creation(self):
		tab = DatabaseTable(model_def = test_model_def)
		tab.create()
		# insert a record
		test_model.insert()

		self.assertTrue(webnotes.conn.sql("select count(*) from `tabTemp Sandbox`")[0][0] == 1)
		# clear
		tab.drop()
		
	def test_db_add_column(self):
		tab = DatabaseTable(model_def = test_model_def)
		tab.create()
		test_model_def.add_model({
			'doctype':'DocField',
			'fieldname':'test_data',
			'label':'Test Data',
			'fieldtype':'Data'
		})
		test_model.test_data1 = 'test1'
		test_model.insert()
		tab.update()
		self.assertTrue(DatabaseRow('tabTemp Sandbox').read(test_data1='test1').test_data1=='test1')
	
	def test_db_add_index(self):
		tab = DatabaseTable(model_def = test_model_def)
		tab.create()
		test_model_def.get_children(fieldname='test_data')[0].index = 1
		tab.update()
		self.assertTrue(tab.is_indexed('test_data'))
		
	def test_db_drop_index(self):
		tab = DatabaseTable(model_def = test_model_def)
		test_model_def.get_children(fieldname='test_data')[0].index = 1
		tab.create()
		self.assertTrue(tab.is_indexed('test_data'))
		test_model_def.get_children(fieldname='test_data')[0].index = 0
		tab.update()
		self.assertFalse(tab.is_indexed('test_data'))
		
	def test_db_add_fkey(self):
		tab = DatabaseTable(model_def = test_model_def)
		tab.create()
		tmp = test_model_def.get_children(fieldname='test_data')[0]
		tmp.fieldtype = 'Link'
		tmp.options = 'Profile'
		tab.update()
		self.assertRaises(test_model.insert, webnotes.InvalidLinkError)
		self.assertTrue(tab.is_indexed('test_data'))
		
		