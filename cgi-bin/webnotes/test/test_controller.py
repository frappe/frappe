"""
	tests for controller
"""
import webnotes
from webnotes.tests import TestCase

class TestController(TestCase):
	def test_controller(self):
		# run this method twice
		from webnotes.model.collection import DatabaseCollection
		collection = DatabaseCollection('Sandbox')
		self.assertTrue(collection.run_method('validate')=='inside validate')