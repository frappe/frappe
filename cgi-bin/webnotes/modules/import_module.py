"""
Imports Documents from modules (.txt) files in the filesystem
"""

import webnotes

def import_module(module, verbose=0):
	"imports the all the records and files from the given module"
	from webnotes.modules import get_module_path
	import os
	
	not_module = ('startup', 'files', 'patches')
	if module in not_module: 
		if verbose: webnotes.msgprint('%s is not a module' % module)
		return
	
	path = get_module_path(module)
	
	doctypes = listfolders(path, 1)
	if 'doctype' in doctypes:
		doctypes.remove('doctype')
		doctypes = ['doctype'] + doctypes
	
	for doctype in doctypes:
		for docname in listfolders(os.path.join(path, doctype), 1):
			import_file(module, doctype, docname, path)
			if verbose: webnotes.msgprint('Imported %s/%s/%s' % (module, doctype, docname))
	
	import_attachments(module)

def get_doclist(path, doctype, docname):
	"returns a doclist (list of dictionaries) of multiple records for the given parameters"
	import os
	from webnotes.model.utils import peval_doclist
	
	do_not_import = ('control_panel')
	
	fname = os.path.join(path,doctype,docname,docname+'.txt')
	if os.path.exists(fname) and (doctype not in do_not_import):
		f = open(fname,'r')
		dl = peval_doclist(f.read())		
		f.close()
		return dl
	else:
		return None

def import_file(module, doctype, docname, path=None):
	"imports a given file into the database"
	
	if not path:
		from webnotes.modules import get_module_path
		path = get_module_path(module)
	
	doclist = get_doclist(path, doctype, docname)
	
	if doclist:
		from webnotes.utils.transfer import set_doc
		set_doc(doclist, 1, 1, 1)

def listfolders(path, only_name=0):
	"""returns the list of folders (with paths) in the given path, 
	if only_name is set, it returns only the folder names"""

	import os
	out = []
	for each in os.listdir(path):
		dirname = each.split(os.path.sep)[-1]
		fullpath = os.path.join(path, dirname)

		if os.path.isdir(fullpath) and not dirname.startswith('.'):
			out.append(only_name and dirname or fullname)
	return out


