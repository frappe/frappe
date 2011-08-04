"""
	tests for controller
"""
import webnotes
from webnotes.run_tests import TestCase

class TestController(TestCase):
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

	def test_controller(self):
		from webnotes.model.collection import DatabaseCollection
		collection = DatabaseCollection('Sandbox')
		self.assertTrue(collection.run_method('validate')=='inside validate')
		
	def test_multi_controller(self):
		from webnotes.model.collection import DatabaseCollection
		collection = DatabaseCollection('Sandbox', models=[self.get_test_model()])
		collection.parent.test_select = 'B'
		self.assertTrue(collection.run_method('validate')=='inside validate 2')
		
		