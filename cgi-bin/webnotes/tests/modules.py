"""
	Tests for modules:
	
	To execute webnotes/tests.py webnotes.tests.modules
	
	Uses Sandbox DocType for testing
"""
import unittest
import webnotes

from webnotes.modules import Module

class ModuleTest(unittest.TestCase):
	def setUp(self):
		webnotes.conn.begin()

	def update_timestamp(self, path):
		"""
			Just open a file for write and save it so that the timetamp changes
		"""
		import os
		path = os.path.join(Module('core').get_path(), path)
		c = file(path,'r').read()
		file(path,'w').write(c)
		
	def test_module_import(self):
		"""
			Import a txt file into the database and check if a new column has been added
		"""
		webnotes.conn.rollback()
		webnotes.conn.sql("alter table tabSandbox drop column `to_be_dropped`", ignore_ddl=1)
		webnotes.conn.begin()
		
		# delete from table
		webnotes.conn.sql("delete from tabDocField where parent='Sandbox' and fieldname='to_be_dropped'")

		self.update_timestamp('doctype/sandbox/sandbox.txt')
		
		# reload
		Module('core').reload('DocType','Sandbox')

		# commit re-adding
		webnotes.conn.commit()

		# check if column created
		self.assertTrue('to_be_dropped' in [r[0] for r in webnotes.conn.sql("desc tabSandbox")])

		# check if imported in table
		self.assertTrue(len(webnotes.conn.sql("select name from tabDocField where parent='Sandbox' and fieldname='to_be_dropped'"))==1)
		
		
	def test_read_js_code(self):
		"""
			Read a js code file
		"""
		data = Module('core').get_doc_file('DocType','Sandbox','.js').read()
		self.assertTrue('//test3456' in data)
		self.assertTrue('//import3456' in data)

	def test_sql_file(self):
		"""
			Test an sql file
		"""
		webnotes.conn.rollback()
		webnotes.conn.sql("drop trigger if exists sandbox_trigger")
		self.update_timestamp('doctype/sandbox/my_trigger.sql')
		Module('core').get_file('doctype','sandbox','my_trigger.sql').sync()
		self.assertTrue(webnotes.conn.sql("show triggers like 'tabSandbox'")[0][0]=='sandbox_trigger')
	
	def test_sync_all(self):
		"""
			Test sync all (rerun the sql file test calling sync_all)
		"""
		webnotes.conn.rollback()
		webnotes.conn.sql("drop trigger if exists sandbox_trigger")
		self.update_timestamp('doctype/sandbox/my_trigger.sql')
		Module('core').sync_all()
		self.assertTrue(webnotes.conn.sql("show triggers like 'tabSandbox'")[0][0]=='sandbox_trigger')
		
	def tearDown(self):
		if webnotes.conn.in_transaction:
			webnotes.conn.rollback()