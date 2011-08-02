"""
Tests for model

TODO:
"""

import unittest
import webnotes

from webnotes.db import Database
from webnotes.db.row import DatabaseRow

class DbTest(unittest.TestCase):
	def setUp(self):
		# connect as per defs
		webnotes.conn.begin()
			
	def test_select(self):
		ret = webnotes.conn.sql("select name from tabProfile where name='Administrator'")
		self.assertTrue(ret[0][0]=='Administrator')
		
	def test_as_dict(self):
		ret = webnotes.conn.sql("select name from tabProfile where name='Administrator'", as_dict=1)
		self.assertTrue(ret[0]['name']=='Administrator')

	def test_insert(self):
		DatabaseRow('tabSandbox', {
			'name':'xSB002',
			'test_data':'aaa'
		}).insert()
		self.assertEquals(webnotes.conn.get_value('Sandbox','xSB002','test_data'), 'aaa')
	
	def test_update(self):
		DatabaseRow('tabSandbox', {
			'name':'xSB002',
			'test_data':'aaa'
		}).insert()
		DatabaseRow('tabSandbox', {
			'name':'xSB002',
			'test_data':'bbb'
		}).update()
		self.assertEquals(webnotes.conn.get_value('Sandbox','xSB002','test_data'), 'bbb')

	def tearDown(self):
		webnotes.conn.rollback()