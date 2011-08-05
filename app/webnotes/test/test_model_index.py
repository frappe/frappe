"""
	Tests for model indexer.
"""

from webnotes.run_tests import TestCase
from webnotes.models.model_index import ModelIndex

test_model_def = FileCollection(raw_models = [
		{
			'name': 'Temp Sandbox',
			'doctype': 'DocType',
			'path': 'core/temp_sandbox'
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

class TestModelIndex(TestCase):
	def write_model(self):
		test_model_def.update()
		
	def test_add_model(self):
		from webnotes.model.collection import FileCollection
		# write a new model

		ModelIndex().index()
		
		# read it into collection
		self.assertTrue(FileCollection('DocType', 'Temp Sandbox').parent.name == 'Temp Sandbox')
	
		# delete it
		test_model_def.delete()
		
	def test_update_model(self):
	
