"""
Imports Documents from modules (.txt) files in the filesystem
"""

import webnotes

#
# imports / updates all files in a module into the database
#
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

#
# get doclist from file
#
def get_doclist(path, doctype, docname):
	"returns a doclist (list of dictionaries) of multiple records for the given parameters"
	import os
	do_not_import = ('control_panel')
	
	fname = os.path.join(path,doctype,docname,docname+'.txt')
	if os.path.exists(fname) and (doctype not in do_not_import):
		f = open(fname,'r')
		dl = eval(f.read())
		f.close()
		return dl
	else:
		return None

#
# import a file into the database
#
def import_file(module, doctype, docname, path=None):
	"imports a given file into the database"
	
	if not path:
		from webnotes.modules import get_module_path
		path = get_module_path(module)
	
	doclist = get_doclist(path, doctype, docname)
	
	if doclist:
		from webnotes.utils.transfer import set_doc
		set_doc(doclist, 1, 1, 1)

#
# list folders in a dir
#
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







# ==============================================================================
# Import from files
# =============================================================================
def import_from_files(modules = [], record_list = [], sync_cp = 0, target_db=None, target_ac=None):

	if target_db or target_ac:
		init_db_login(target_ac, target_db)

	from webnotes.utils import transfer
	# Get paths of folder which will be imported
	folder_list = get_folder_paths(modules, record_list)
	ret = []
		
	if folder_list:
		# get all doclist
		all_doclist = get_all_doclist(folder_list)
	
		# import doclist
		ret += accept_module(all_doclist)
	
		# import attachments
		for m in modules:
			import_attachments(m)
		
		# sync control panel
		if sync_cp:
			ret.append(sync_control_panel())
	else:
		ret.append("Module/Record not found")
		
	return ret


# ==============================================================================
# Get list of folder path
# =============================================================================
# record_list in format [[module,dt,dn], ..]
def get_folder_paths(modules, record_list):
	import os
	import webnotes
	import fnmatch
	import webnotes.defs
	from webnotes.modules import transfer_types, get_module_path, scrub

	folder_list=[]

	# get the folder list
	if record_list:
		for record in record_list:
			if scrub(record[1]) in ('doctype', 'page', 'search_criteria'):
				record[1], record[2] = scrub(record[1]), scrub(record[2])
			
			folder_list.append(os.path.join(get_module_path(scrub(record[0])), \
				record[1], record[2].replace('/','_')))

	if modules:
		# system modules will be transferred in a predefined order and before all other modules
		sys_mod_ordered_list = ['roles', 'core','application_internal', 'mapper', 'settings']
		all_mod_ordered_list = [t for t in sys_mod_ordered_list if t in modules] + list(set(modules).difference(sys_mod_ordered_list))
				
		for module in all_mod_ordered_list:
			mod_path = get_module_path(module)
			types_list = listfolders(mod_path, 1)
			
			# list of types
			types_list = list(set(types_list).difference(['control_panel']))
			all_transfer_types =[t for t in transfer_types if t in types_list] + list(set(types_list).difference(transfer_types))
			
			# build the folders
			for d in all_transfer_types:
				if d not in  ('files', 'startup', 'patches'):
					# get all folders inside type
					folder_list+=listfolders(os.path.join(mod_path, d))

	return folder_list

	
# ==============================================================================
# Get doclist for all folder
# =============================================================================


def get_all_doclist(folder_list):
	import fnmatch
	import os
		
	doclist = []
	all_doclist = []

	# build into doclist
	for folder in folder_list:
		# get the doclist
		file_list = os.listdir(folder)
		for each in file_list:

			if fnmatch.fnmatch(each,'*.txt'):
				doclist = eval(open(os.path.join(folder,each),'r').read())
				# add code
				all_doclist.append(doclist)
	
	return all_doclist
	

# ==============================================================================
# accept a module coming from a remote server
# ==============================================================================
def accept_module(super_doclist):
	import webnotes
	import webnotes.utils
	from webnotes.utils import transfer
	msg, i = [], 0
	
	for dl in super_doclist:
		if dl[0]['doctype']!='Control Panel':
			msg.append(transfer.set_doc(dl, 1, 1, 1))
		
		if dl[0]['doctype']=='Module Def':
			update_module_timestamp(dl[0]['name'])

	if not webnotes.conn.in_transaction:
		webnotes.conn.sql("START TRANSACTION")
	
	# clear cache
	webnotes.conn.sql("DELETE from __DocTypeCache")
	webnotes.conn.sql("COMMIT")
	
	return msg

# =============================================================================
# Update timestamp in Module Def table
# =============================================================================
def update_module_timestamp(mod):
	import webnotes, webnotes.defs, os
	
	try:
		file = open(os.path.join(webnotes.defs.modules_path, mod, 'module.info'), 'r')
	except Exception, e:
		if e.args[0]==2:
			return # module.info
		else:
			raise e
			
	module_info = eval(file.read())
	file.close()

# =============================================================================

def update_module_timestamp_query(mod, timestamp):
	import webnotes
	webnotes.conn.sql("start transaction")
	webnotes.conn.sql("update `tabModule Def` set last_updated_date=%s where name=%s", (timestamp, mod))
	webnotes.conn.sql("commit")


# =============================================================================
# Import Attachments
# =============================================================================

def import_attachments(m):
	import os, webnotes.defs
	import webnotes.utils.file_manager
	from webnotes.modules import get_module_path
	
	out = []
	
	# get list
	try:
		folder = os.path.join(get_module_path(m), 'files')
		fl = os.listdir(folder)
	except OSError, e:
		if e.args[0]==2:
			return
		else:
			raise e
	
	# import files
	for f in fl:
		if not os.path.isdir(os.path.join(folder, f)):
			# delete
			webnotes.utils.file_manager.delete_file(f)
		
			# import
			file = open(os.path.join(folder, f),'r')
			webnotes.utils.file_manager.save_file(f, file.read(), m)
			file.close()
			
			out.append(f)
	
	return out
