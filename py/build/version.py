"""
	Version Control:
	
	Schema:
	
	properties (key, value)
	uncommitted (fname, ftype, content, timestamp)
	files (fname, ftype, content, timestamp, version)
	log (fname, ftype, version)
	bundle_files (fname primary key)
	
	Discussion:
	
	There are 2 databases, versions.db and versions-local.db
	
	All changes are commited to versions-local.db, when the patches are complete, the developer
	must pull the latest .wnf db and merge
	
	versions-local.db is never commited in the global repository
"""

import unittest
import os

test_file = {'fname':'test.js', 'ftype':'js', 'content':'test_code', 'timestamp':'1100'}
root_path = os.curdir

def edit_file():
	# edit a file
	p = os.path.join(root_path, 'lib/js/core.js')

	# read
	f1 = open(p, 'r')
	content = f1.read()
	f1.close()
	
	# write
	f = open(p, 'w')
	f.write(content)
	f.close()
	return os.path.relpath(p, root_path)
		
verbose = False

class TestVC(unittest.TestCase):
	def setUp(self):
		self.vc = VersionControl(root_path, True)
		self.vc.repo.setup()
	
	def test_add(self):
		self.vc.add(**test_file)
		ret = self.vc.repo.sql('select * from uncommitted', as_dict=1)[0]		
		self.assertTrue(ret['content']==test_file['content'])
	
	def test_commit(self):
		last_number = self.vc.repo.get_value('last_version_number')
		self.vc.add(**test_file)
		self.vc.commit()

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
		self.vc.add(**test_file)
		self.vc.commit()
		self.assertTrue(self.vc.repo.diff(None), ['test.js'])

	def test_walk(self):
		# add
		self.vc.add_all()

		# check if added
		ret = self.vc.repo.sql("select * from uncommitted", as_dict=1)
		self.assertTrue(len(ret)>0)

		self.vc.commit()

		p = edit_file()
		# add
		self.vc.add_all()

		# check if added
		ret = self.vc.repo.sql("select * from uncommitted", as_dict=1)
		self.assertTrue(p in [r['fname'] for r in ret])

	def test_merge(self):
		self.vc.add_all()
		
		self.vc.commit()
		
		# write the file
		self.vc.repo.conn.commit()

		# make master (copy)
		self.vc.setup_master()

		p = edit_file()
		
		self.vc.add_all()
		self.vc.commit()
				
		self.vc.merge(self.vc.repo, self.vc.master)
		
		log = self.vc.master.diff(int(self.vc.master.get_value('last_version_number'))-1)
		self.assertTrue(p in log)
				
	def tearDown(self):
		self.vc.close()
		if os.path.exists(self.vc.local_db_name()):
			os.remove(self.vc.local_db_name())
		if os.path.exists(self.vc.master_db_name()):
			os.remove(self.vc.master_db_name())

class VersionControl:
	def __init__(self, root=None, testing=False):
		self.testing = testing

		self.set_root(root)

		self.repo = Repository(self, self.local_db_name())
		self.ignore_folders = ['.git', '.', '..']
		self.ignore_files = ['py', 'pyc', 'DS_Store', 'txt', 'db-journal', 'db']
	
	def local_db_name(self):
		"""return local db name"""
		return os.path.join(self.root_path, 'versions-local.db' + (self.testing and '.test' or ''))

	def master_db_name(self):
		"""return master db name"""
		return os.path.join(self.root_path, 'versions-master.db' + (self.testing and '.test' or ''))
	
	def setup_master(self):
		"""
			setup master db from local (if not present)
		"""
		import os
		if not os.path.exists(self.master_db_name()):
			os.system('cp %s %s' % (self.local_db_name(), self.master_db_name()))

		self.master = Repository(self, self.master_db_name())
	
	def set_root(self, path=None):
		"""
			set / reset root and connect
			(the root path is the path of the folder)
		"""
		import os
		if not path:
			path = os.path.abspath(os.path.curdir)
		
		self.root_path = path
	
	def relpath(self, fname):
		"""
			get relative path from root path
		"""
		import os
		return os.path.relpath(fname, self.root_path)
	
	def timestamp(self, path):
		"""
			returns timestamp
		"""
		import os
		if os.path.exists(path):
			return int(os.stat(path).st_mtime)
		else:
			return 0

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
				fpath = os.path.join(wt[0], fname)

				if fname.endswith('build.json'):
					self.repo.add_bundle(fpath)
					continue
				
				if fname.split('.')[-1] in self.ignore_files:
					# nothing to do
					continue
								
				# file does not exist
				if not self.exists(fpath):
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
				print 'merging %s' % f['fname']
				target.add(**f)
			
			target.commit(d[0])			
	
	"""
		short hand
	"""
	def commit(self, version=None): 
		"""commit to local"""
		self.repo.commit(version)
		
	def add(self, **args):
		"""add to local"""
		self.repo.add(**args)

	def remove(self, fname):
		"""remove from local"""
		self.repo.add(fname=fname, action='remove')
		
	def exists(self, fname):
		"""exists in local"""
		return len(self.repo.sql("select fname from files where fname=?", (self.relpath(fname),)))
				
	def get_file(self, fname):
		"""return file"""
		return self.repo.sql("select * from files where fname=?", (self.relpath(fname),), as_dict=1)[0]
		
		
	def close(self):
		self.repo.conn.commit()
		self.repo.conn.close()
		
		if hasattr(self, 'master'):
			self.master.conn.commit()
			self.master.conn.close()
	
	
	
	
class Repository:
	def __init__(self, vc, fname):
		self.vc = vc

		import sqlite3
		
		self.db_path = os.path.join(self.vc.root_path, fname)
		self.conn = sqlite3.connect(self.db_path)
		self.cur = self.conn.cursor()

	def setup(self):
		"""
			setup the schema
		"""
		print "setting up %s..." % self.db_path
		self.cur.executescript("""
		create table properties(pkey primary key, value);
		create table uncommitted(fname primary key, ftype, content, timestamp, action);
		create table files (fname primary key, ftype, content, timestamp, version);
		create table log (fname, ftype, version);
		create table versions (number integer primary key, version);
		create table bundles(fname primary key);
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

		
	def add(self, fname, ftype=None, timestamp=None, content=None, version=None, action=None):
		"""
			add to uncommitted
		"""
		import os

		if not timestamp:
			timestamp = self.vc.timestamp(fname)

		# commit relative path
		fname = self.vc.relpath(fname)
				
		if not action:
			action = 'add'
			
		if not ftype:
			ftype = fname.split('.')[-1]
					
		self.sql("insert or replace into uncommitted(fname, ftype, timestamp, content, action) values (?, ?, ?, ?, ?)" \
			, (fname, ftype, timestamp, content, action))
	
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
		if not version: version = self.new_version()

		self.update_number(version)

		# find added files to commit
		self.add_from_uncommitted(version)
						
		# clear uncommitted
		self.sql("delete from uncommitted")
	
	
	def add_from_uncommitted(self, version):
		"""
			move files from uncommitted table to files table
		"""
		
		added = self.sql("select * from uncommitted", as_dict=1)
		for f in added:
			if f['action']=='add':
				# move them to "files"
				self.sql("""
					insert or replace into files 
					(fname, ftype, timestamp, content, version) 
					values (?,?,?,?,?)
					""", (f['fname'], f['ftype'], f['timestamp'], f['content'], version))

			elif f['action']=='remove':
				self.sql("""delete from files where fname=?""", (f['fname'],))
			
			else:
				raise Exception, 'bad action %s' % action
			
			# update log
			self.add_log(f['fname'], f['ftype'], version)	
	
	def timestamp(self, fname):
		"""
			get timestamp
		"""
		fname = self.vc.relpath(fname)
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
	
	def uncommitted(self):
		"""
			return list of uncommitted files
		"""
		return [f[0] for f in self.sql("select fname from uncommitted")]
	
	def add_log(self, fname, ftype, version):
		"""
			add file to log
		"""
		self.sql("insert into log(fname, ftype, version) values (?,?,?)", (fname, ftype, version))
	
	def add_bundle(self, fname):
		"""
			add to bundles
		"""
		self.sql("insert or replace into bundles(fname) values (?)", (fname,))
		
if __name__=='__main__':
	import os, sys
	sys.path.append('py')
	sys.path.append('lib/py')
	unittest.main()