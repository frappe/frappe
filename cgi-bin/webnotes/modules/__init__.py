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
	return get_file_timestamp(get_item_file(module, dt, dn))

def get_file_timestamp(fn):
	"""
		Returns timestamp of the given file
	"""
	import os
	from webnotes.utils import cint
	
	try:
		return str(cint(os.stat(fn).st_mtime))
	except OSError, e:
		if e.args[0]!=2:
			raise e
		else:
			return None
			
def get_module_path(module):
	"""
		Returns path of the given module (imports it and reads it from __file__)
	"""
	import webnotes.defs, os, os.path
	
	try:
		exec ('import ' + scrub(module)) in locals()
		modules_path = eval(scrub(module) + '.__file__')
		
		modules_path = os.path.sep.join(modules_path.split(os.path.sep)[:-1])
	except ImportError, e:
		# get module path by importing the module
		modules_path = os.path.join(webnotes.defs.modules_path, scrub(module))
		
	return modules_path