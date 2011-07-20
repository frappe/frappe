"""
	Utilities for using modules
"""

transfer_types = ['Role', 'Print Format','DocType','Page','DocType Mapper','GL Mapper','Search Criteria', 'Patch']

def scrub(txt):
	return txt.replace(' ','_').replace('-', '_').replace('/', '_').lower()

def scrub_dt_and_dn(dt, dn):
	"""
		Returns in lowercase and code friendly names of doctype and name for certain types
	"""
	ndt, ndn = dt, dn
	if dt.lower() in ('doctype', 'search criteria', 'page'):
		ndt, ndn = scrub(dt), scrub(dn)

	return ndt, ndn

def get_item_file(module, dt, dn):
	"""
		Returns the path of the item file
	"""
	import os
	ndt, ndn = scrub_dt_and_dn(dt, dn)

	return os.path.join(get_module_path(module), ndt, ndn, ndn + '.txt')
	
def get_item_timestamp(module, dt, dn):
	"""
		Return ths timestamp of the given item (if exists)
	"""
	from webnotes.utils import get_file_timestamp
	return get_file_timestamp(get_item_file(module, dt, dn))

			
def get_module_path(module):
	"""
		Returns path of the given module (imports it and reads it from __file__)
	"""
	return Module(module).get_path()
	
def switch_module(dt, dn, to, frm=None, export=None):
	"""
		Change the module of the given doctype, if export is true, then also export txt and copy
		code files from src
	"""
	import os
	webnotes.conn.sql("update `tab"+dt+"` set module=%s where name=%s", (to, dn))

	if export:
		export_doc(dt, dn)

		# copy code files
		if dt in ('DocType', 'Page', 'Search Criteria'):
			from_path = os.path.join(get_module_path(frm), scrub(dt), scrub(dn), scrub(dn))
			to_path = os.path.join(get_module_path(to), scrub(dt), scrub(dn), scrub(dn))

			# make dire if exists
			os.system('mkdir -p %s' % os.path.join(get_module_path(to), scrub(dt), scrub(dn)))

			for ext in ('py','js','html','css'):
				os.system('cp %s %s')





class Module:
	"""
		Represents a module in the framework
	"""
	def __init__(self, name):
		self.name = name
	
	def get_path(self):
		"""
			Returns path of the module (imports it and reads it from __file__)
		"""
		import webnotes.defs, os

		try:
			exec ('import ' + scrub(self.name)) in locals()
			modules_path = eval(scrub(self.name) + '.__file__')

			modules_path = os.path.sep.join(modules_path.split(os.path.sep)[:-1])
		except ImportError, e:
			modules_path = os.path.join(webnotes.defs.modules_path, scrub(self.name))

		return modules_path
				
	def get_file(self, *path):
		"""
			Returns ModuleFile object, in path specifiy the package name and file name
			For example::
				Module('accounts').get_file('doctype','account.txt')
		"""
		return ModuleFile(self, os.path.join(self.get_path(), os.path.join(*path)))
	
class ModuleFile:
	"""
		Module file class
	"""
	
	def __init__(self, path):
		self.path = os.path.join(*path)
		
	def is_new(self):
		"""
			Returns true if file does not match with last updated timestamp
		"""
		import webnotes.utils
		self.timestamp = webnotes.utils.get_file_timestamp(self.path)
		
		if self.timestamp != self.get_db_timestamp():
			return True
		
	def get_db_timestamp(self):
		"""
			Returns the timestamp of the file
		"""
		try:
			ts = webnotes.conn.sql("select tstamp from __file_timestamp where file_name=%s", fn)
			if ts:
				return ts[0][0]
		except Exception, e:
			if e.args[0]==1147:
				# create the table
				webnotes.conn.commit()
				webnotes.conn.sql("""
					create table __file_timestamp (
						file_name varchar(180) primary key, 
						tstamp varchar(40))""")
				webnotes.conn.begin()
			else:
				raise e
						
	def update(self):
		"""
			Update the timestamp into the database
			(must be called after is_new)
		"""
		webnotes.conn.sql("""
			insert into __file_timestamp(file_name, tstamp) 
			values (%s, %s) on duplicate key update""", (self.path, self.timestamp))

	def read(self):
		"""
			Return the file content
		"""
		return open(self.path,'r').read()