"""
	Utilities for using modules
"""
import webnotes

transfer_types = ['Role', 'Print Format','DocType','Page','DocType Mapper','GL Mapper','Search Criteria', 'Patch']

def scrub(txt):
	return txt.replace(' ','_').replace('-', '_').replace('/', '_').lower()

def scrub_dt_dn(dt, dn):
	"""
		Returns in lowercase and code friendly names of doctype and name for certain types
	"""
	ndt, ndn = dt, dn
	if dt.lower() in ('doctype', 'search criteria', 'page'):
		ndt, ndn = scrub(dt), scrub(dn)

	return ndt, ndn

def get_module_name(dt):
	"""
		Return the module type
	"""
	return webnotes.conn.sql("select module from tabDocType where name=%s", dt)[0][0]

def get_item_file(module, dt, dn):
	"""
		Returns the path of the item file
	"""
	import os
	ndt, ndn = scrub_dt_dn(dt, dn)

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

def get_doc_path(dt, dn, module=None):
	"""
		Return the path to a particular doc folder
	"""
	import os
	
	if not module:
		if dt=='Module Def': 
			module=dn
		else:
			module = webnotes.conn.get_value(dt, dn, 'module')

	ndt, ndn = scrub_dt_dn(dt, dn)

	return os.path.join(get_module_path(module), ndt, ndn)

def reload_doc(module, dt, dn):
	"""
		Sync a file from txt to module
		Alias for::
			Module(module).reload(dt, dn)
	"""
	Module(module).reload(dt, dn)


class ModuleManager:
	"""
		Module manager class, used to run functions on all modules
	"""
	
	def get_all_modules(self):
		"""
			Return list of all modules
		"""
		import webnotes.defs
		from webnotes.modules.utils import listfolders

		if hasattr(webnotes.defs, 'modules_path'):
			return listfolders(webnotes.defs.modules_path, 1)


class Module:
	"""
		Represents a module in the framework, has classes for syncing files
	"""
	def __init__(self, name):
		self.name = name
		self.path = None
		self.sync_types = ['txt','sql']
		self.code_types = ['js','css','py','html','sql']
	
	def get_path(self):
		"""
			Returns path of the module (imports it and reads it from __file__)
		"""
		if not self.path:

			import webnotes.defs, os

			try:
				# by import
				exec ('import ' + scrub(self.name)) in locals()
				self.path = eval(scrub(self.name) + '.__file__')
				self.path = os.path.sep.join(self.path.split(os.path.sep)[:-1])
			except ImportError, e:
				# force
				self.path = os.path.join(webnotes.defs.modules_path, scrub(self.name))
				
 		return self.path				
	
	def get_doc_file(self, dt, dn, extn='.txt'):
		"""
			Return file of a doc
		"""
		dt, dn = scrub_dt_dn(dt, dn)
		return self.get_file(dt, dn, dn + extn)
		
	def get_file(self, *path):
		"""
			Returns ModuleFile object, in path specifiy the package name and file name
			For example::
				Module('accounts').get_file('doctype','account','account.txt')
		"""
		import os
		
		path = os.path.join(self.get_path(), os.path.join(*path))

		if path.endswith('.txt'):
			from webnotes.modules.module_file_txt import ModuleFileTxt
			return ModuleFileTxt(path)

		if path.endswith('.sql'):
			from webnotes.modules.module_file_sql import ModuleFileSql
			return ModuleFileSql(path)

		if path.endswith('.js'):
			from webnotes.modules.module_file_js import ModuleFileJs
			return ModuleFileJs(path)

		else:
			from webnotes.modules.module_file import ModuleFile
			return ModuleFile(path)
	
	def reload(self, dt, dn):
		"""
			Sync the file to the db
		"""
		dt, dn = scrub_dt_dn(dt, dn)
		self.get_file(dt, dn, dn + '.txt').sync()
		
	def sync_all_of_type(self, extn, verbose=0):
		"""
			Walk through all the files in the modules and sync all files of
			a particular type
		"""
		import os
		ret = []
		for walk_tuple in os.walk(self.get_path()):
			for f in walk_tuple[2]:
				if f.split('.')[-1] == extn:
					path = os.path.relpath(os.path.join(walk_tuple[0], f), self.get_path())
					self.get_file(path).sync()
					if verbose:
						print 'complete: ' + path

	def sync_all(self, verbose=0):
		"""
			Walk through all the files in the modules and sync all files
		"""
		import os
		self.sync_all_of_type('txt', verbose)
		self.sync_all_of_type('sql', verbose)
