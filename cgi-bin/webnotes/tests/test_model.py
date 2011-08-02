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

from webnotes.model import get_model

class TestModel(unittest.TestCase):
	def setUp(self):
		webnotes.conn.begin()
		
	def test_insert(self):
		"""
			test model insertion
		"""
		m = get_model(attributes = {
			'doctype':'Sandbox',
			'test_data': 'value',
			'test_date': '2011-01-22'
		})
		m.insert()
		self.assertEquals(get_model('Sandbox',m.name).test_data, 'value')
		
	