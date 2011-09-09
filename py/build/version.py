"""
	Version Control:
	
	Schema:
	
	properties (key, value)
	uncommitted (fname, ftype, content, timestamp)
	files (fname, ftype, content, timestamp, version)
	
"""

import unittest
import os

root_path = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..'))
testfile = os.path.join(root_path, 'js/core.js')

class TestVC(unittest.TestCase):
	def setUp(self):
		self.vc = VersionControl(root_path)
		self.vc.setup()
	
	def test_add(self):
		test_file = {'fname':'test.js', 'ftype':'js', 'content':'test_code', 'timestamp':'1100'}
		self.vc.repo.add(**test_file)
		ret = self.vc.sql('select * from uncommitted', as_dict=1)[0]
		self.assertTrue(ret==test_file)
	
	def tearDown(self):
		self.vc.close()
		os.remove(os.path.join(root_path, '.wnf'))
		
class VersionControl:
	def __init__(self, root):
		self.repo = Repository(self)
		self.root(root)
	
	def setup(self):
		"""
			setup the schema
		"""
		self.cur.executescript("""
		create table properties(key, value);
		create table uncommitted(fname, ftype, content, timestamp);
		create table files(fname, ftype, content, timestamp, version);
		""")
	
	def root(self, path=None):
		"""
			set / reset root and connect
		"""
		if path:
			self.root_path = path
		else:
			return self.root_path

		import sqlite3
		self.conn = sqlite3.connect(os.path.join(self.root_path, '.wnf'))
		self.cur = self.conn.cursor()
		
	def sql(self, query, values=(), as_dict=None):
		"""
			like webnotes.db.sql
		"""
		self.cur.execute(query, values)
		res = self.cur.fetchall()
		
		if as_dict:
			out = []
			for row in res:
				d = {}
				for idx, col in enumerate(self.cur.description):
					d[col[0]] = row[idx]
				out.append(d)
			return out
			
		return res
			
		
	def init(self):
		"""
			crate a .wnf db in the rool path to store the versions
		"""
		pass
	
	def ignore(self, fname):
		"""
			update ignore list
		"""
		pass
	
	
	def add_all(self):
		"""
			walk the root folder Add all dirty files to the vcs
		"""
		pass
		
	def commit(self, comment=None):
		"""
			commit added files to the repository
		"""
		pass
		
	def close(self):
		self.conn.close()
		
class Repository:
	def __init__(self, vc):
		self.vc = vc
		
	def add(self, fname, ftype, timestamp, content=None):
		"""
			add to uncommitted
		"""
		self.vc.sql("insert into uncommitted(fname, ftype, timestamp, content) values (?, ?, ?, ?)" \
			, (fname, ftype, timestamp, content))
		
	def commit(self, version):
		"""
			copy uncommitted files to repository, update the log and add the change
		"""
		pass
		
class Log:
	def __init__(self, vc):
		self.vc = vc
		
	def add_to_log(self, version, fname, ftype):
		"""
			add file to log
		"""
		pass
		
	def get_diff(self, from_version, to_version=None):
		"""
			get list of files changed between versions
		"""
		pass
		
if __name__=='__main__':
	unittest.main()