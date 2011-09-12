"""
	Version Control:
	
	Schema:
	
	properties (key, value)
	uncommitted (fname, ftype, content, timestamp)
	files (fname, ftype, content, timestamp, version)
	log (fname, ftype, version)
	
	Discussion:
	
	There are 2 databases, versions.db and versions-local.db
	
	All changes are commited to versions-local.db, when the patches are complete, the developer
	must pull the latest .wnf db and merge
	
	versions-local.db is never commited in the global repository
	
TODO

	- walk
	- merge
	- client
"""

import unittest
import os

root_path = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..'))
test_file = {'fname':'test.js', 'ftype':'js', 'content':'test_code', 'timestamp':'1100'}

def edit_file():
	# edit a file
	p = os.path.join(root_path, 'js/core.min.js')
	content = open(p, 'r').read()
	f = open(p, 'w')
	f.write(content)
	f.close()
	return p
		
verbose = False

class TestVC(unittest.TestCase):
	def setUp(self):
		self.vc = VersionControl(root_path)
		self.vc.repo.setup()
	
	def test_add(self):
		self.vc.repo.add(**test_file)
		ret = self.vc.repo.sql('select * from uncommitted', as_dict=1)[0]
		self.assertTrue(ret==test_file)
	
	def test_commit(self):
		last_number = self.vc.repo.get_value('last_version_number')
		self.vc.repo.add(**test_file)
		self.vc.repo.commit()

		# test version
		number = self.vc.repo.get_value('last_version_number')
		version = self.vc.repo.sql("select version from versions where number=?", (number,))[0][0]
		self.assertTrue(number != last_number)

		# test file
		self.assertTrue(self.vc.repo.get_file('test.js')['content'] == test_file['content'])
		
		# test uncommitted
		self.assertFalse(self.vc.repo.sql("select * from uncommitted"))
	
		# test log
		self.assertTrue(self.vc.repo.sql("select * from log where version=?", (version,)))

	def test_diff(self):
		self.vc.repo.add(**test_file)
		self.vc.repo.commit()
		self.assertTrue(self.vc.repo.diff(None), ['test.js'])

	def test_walk(self):
		# add
		self.vc.add_all()

		# check if added
		ret = self.vc.repo.sql("select * from uncommitted", as_dict=1)
		self.assertTrue(len(ret)>0)

		self.vc.repo.commit()

		p = edit_file()

		# add
		self.vc.add_all()

		# check if added
		ret = self.vc.repo.sql("select * from uncommitted", as_dict=1)
		self.assertTrue(ret[0]['fname']==p)

	def test_merge(self):
		self.vc.add_all()
		
		self.vc.repo.commit()
		
		# write the file
		self.vc.repo.conn.commit()

		# make master (copy)
		os.system('cp %s %s' % (os.path.join(root_path, 'versions-local.db'), os.path.join(root_path, 'versions-master.db')))
		self.vc.setup_master()

		p = edit_file()
		
		self.vc.add_all()
		self.vc.repo.commit()
				
		self.vc.merge(self.vc.repo, self.vc.master)
		
		log = self.vc.master.diff(int(self.vc.master.get_value('last_version_number'))-1)
		self.assertTrue(log, [p])
				
	def tearDown(self):
		self.vc.close()
		os.remove(self.vc.repo.db_path)




class VersionControl:
	def __init__(self, root):
		#self.master = Repository(self, 'versions-master.db')
		self.root(root)

		self.repo = Repository(self, 'versions-local.db')
		self.ignore_folders = ['.git', '.', '..']
		self.ignore_files = ['pyc', 'DS_Store', 'txt', 'db-journal', 'db']
	
	def setup_master(self):
		self.master = Repository(self, 'versions-master.db')
	
	def root(self, path=None):
		"""
			set / reset root and connect
		"""
		if path:
			self.root_path = path
		else:
			return self.root_path
	
	def timestamp(self, path):
		"""
			returns timestamp
		"""
		import os
		return int(os.stat(path).st_mtime)

	def add_all(self):
		"""
			walk the root folder Add all dirty files to the vcs
		"""
		import os
		for wt in os.walk(self.root_path, followlinks = True):
			
			# ignore folders
			for folder in self.ignore_folders:
				if folder in wt[1]:
					wt[1].remove(folder)
					
			for fname in wt[2]:
				if fname.split('.')[-1] in self.ignore_files:
					# nothing to do
					continue
					
				fpath = os.path.join(wt[0], fname)
				
				# file does not exist
				if not self.repo.exists(fpath):
					if verbose:
						print "%s added" % fpath
					self.repo.add(fpath)
					
				# file changed
				else:
					if self.timestamp(fpath) != self.repo.timestamp(fpath):
						if verbose:
							print "%s changed" % fpath
						self.repo.add(fpath)
	
	def version_diff(self, source, target):
		"""
			get missing versions in target
		"""
		# find versions in source not in target
		d = []
		
		versions = source.sql("select version from versions")
		for v in versions:
			if not target.sql("select version from versions where version=?", v):
				d.append(v)

		return d
		
	def merge(self, source, target):
		"""
			merges with two repositories
		"""
		for d in self.version_diff(source, target):
			for f in source.sql("select * from files where version=?", d, as_dict=1):
				target.add(**f)
			
			target.commit(d[0])			

	def close(self):
		self.repo.conn.close()
		
class Repository:
	def __init__(self, vc, fname = 'versions-local.db'):
		self.vc = vc

		import sqlite3
		self.db_path = os.path.join(self.vc.root_path, fname)
		self.conn = sqlite3.connect(self.db_path)
		self.cur = self.conn.cursor()

	def setup(self):
		"""
			setup the schema
		"""
		self.cur.executescript("""
		create table properties(pkey primary key, value);
		create table uncommitted(fname primary key, ftype, content, timestamp);
		create table files (fname primary key, ftype, content, timestamp, version);
		create table log (fname, ftype, version);
		create table versions (number integer primary key, version);
		""")
		
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

	def get_value(self, key):
		"""
			returns value of a property
		"""
		ret = self.sql("select `value` from properties where `pkey`=?", (key,))
		return ret and ret[0][0] or None

	def set_value(self, key, value):
		"""
			returns value of a property
		"""
		self.sql("insert or replace into properties(pkey, value) values (?, ?)", (key,value))

		
	def add(self, fname, ftype=None, timestamp=None, content=None, version=None):
		"""
			add to uncommitted
		"""
		if not ftype:
			ftype = fname.split('.')[-1]
			
		if not timestamp:
			timestamp = self.vc.timestamp(fname)
		
		self.sql("insert into uncommitted(fname, ftype, timestamp, content) values (?, ?, ?, ?)" \
			, (fname, ftype, timestamp, content))
	
	def new_version(self):
		"""
			return a random version id
		"""
		import random
		
		# genarate id (global)
		return '%016x' % random.getrandbits(64)

	def update_number(self, version):
		"""
			 update version.number
		"""
		# set number (local)
		self.sql("insert into versions (number, version) values (null, ?)", (version,))
		number =  self.sql("select last_insert_rowid()")[0][0]
		self.set_value('last_version_number', number)
	
	def commit(self, version=None):
		"""
			copy uncommitted files to repository, update the log and add the change
		"""
		# get a new version number
		if not version:
			version = self.new_version()

		self.update_number(version)

		# find added files to commit
		added = self.sql("select * from uncommitted", as_dict=1)
		for f in added:
			
			# move them to "files"
			self.sql("""
				insert or replace into files 
				(fname, ftype, timestamp, content, version) 
				values (?,?,?,?,?)
				""", (f['fname'], f['ftype'], f['timestamp'], f['content'], version))
				
			# update log
			self.add_log(f['fname'], f['ftype'], version)
						
		# clear uncommitted
		self.sql("delete from uncommitted")
	
	def exists(self, fname):
		"""
			true if exists
		"""
		return self.sql("select fname from files where fname=?", (fname,))

	def timestamp(self, fname):
		"""
			get timestamp
		"""
		return int(self.sql("select timestamp from files where fname=?", (fname,))[0][0] or 0)

	def diff(self, number):
		"""
			get changed files since number
		"""
		if number is None: number = 0
		ret = self.sql("""
			select log.fname from log, versions 
			where versions.number > ? 
			and versions.version = log.version""", (number,))
			
		return list(set([f[0] for f in ret]))
	
	def get_file(self, fname):
		"""
			return file info as dict
		"""
		return self.sql("select * from files where fname=?", (fname,), as_dict=1)[0]
		
	def add_log(self, fname, ftype, version):
		"""
			add file to log
		"""
		self.sql("insert into log(fname, ftype, version) values (?,?,?)", (fname, ftype, version))
		
		
if __name__=='__main__':
	unittest.main()