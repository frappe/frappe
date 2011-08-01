"""
Tests for model

TODO:
"""

import unittest
import webnotes

from webnotes.db import Database, DatabaseRecord

class DbTest(unittest.TestCase):
	def setUp(self):
		# connect as per defs
		self.db = Database()
		self.db.begin()
			
	def test_select(self):
		ret = self.db.sql("select name from tabProfile where name='Administrator'")
		self.assertTrue(ret[0][0]=='Administrator')
		
	def test_as_dict(self):
		ret = self.db.sql("select name from tabProfile where name='Administrator'", as_dict=1)
		self.assertTrue(ret[0]['name']=='Administrator')

	def test_insert(self):
		DatabaseRecord('Sandbox', {
			'name':'xSB001'
			'test_data':'aaa'
		}).insert()
		assertEquals(self.db.get_value('Sandbox','xSB001','test_data'), 'aaa')
	
	def test_update(self):
		DatabaseRecord('Sandbox', {
			'name':'xSB001'
			'test_data':'aaa'
		}).insert()
		DatabaseRecord('Sandbox', {
			'name':'SB0xSB00101'
			'test_data':'bbb'
		}).update()
		assertEquals(self.db.get_value('Sandbox','xSB001','test_data'), 'bbb')

	def tearDown(self):
		self.db.rollback()