# ==============================================================================
# export to files
# ==============================================================================

updated_modules = []

from webnotes.modules import scrub, get_module_path

def export_to_files(modules = [], record_list=[], from_db=None, from_ac=None, verbose=1, record_module=None):
	# Multiple doctype  and multiple modules export to be done
	# for Module Def, right now using a hack..should consider table update in the next version
	# all modules transfer not working, because source db not known
	# get the items
	
	global updated_modules

	if from_ac or from_db:
		init_db_login(from_ac, from_db)
	
	out = []
	import webnotes.model.doc
	module_doclist =[]
	if record_list:
		for record in record_list:
			module_doclist.append([d.fields for d in webnotes.model.doc.get(record[0], record[1])])
		
	# build the doclist
	if modules:
		for m in modules:
			module_doclist +=get_module_doclist(m)
			
	# write files
	for doclist in module_doclist:
		if verbose:
			out.append("Writing for " + doclist[0]['doctype'] + " / " + doclist[0]['name'])
		write_document_file(doclist, record_module)
	
	# write out attachments
	for m in modules:
		write_attachments(m)
	
	return out

# ==============================================================================
# write module.info file with last updated timestamp
# ==============================================================================

def write_attachments(m):
	import webnotes, os
	from webnotes.utils.file_manager import get_file

	try:
		fl = webnotes.conn.sql("select name from `tabFile Data` where module=%s", m)
	except Exception, e:
		if e.args[0]==1054: # no field called module
			return
		else:
			raise e
	
	# write the files	
	if fl:
		folder = os.path.join(webnotes.defs.modules_path, m, 'files')
		webnotes.create_folder(folder)
		for f in fl:
			file_det = get_file(f)
			file = open(os.path.join(folder, file_det[0]), 'w+')
			file.write(file_det[1])
			file.close()		
		
	
# ==============================================================================
# write module.info file with last updated timestamp
# ==============================================================================

def write_module_info(mod):
	import webnotes.utils, os

	file = open(os.path.join(get_module_path(mod), 'module.info'), 'w')
	file.write(str({'update_date': webnotes.utils.now()}))
	file.close()
	
# ==============================================================================
# prepare a list of items in a module
# ==============================================================================

def get_module_items(mod):
	import webnotes
	from webnotes.modules import transfer_types
	from webnotes.modules import scrub

	dl = []
	for dt in transfer_types:
		try:
			dl2 = webnotes.conn.sql('select name, modified from `tab%s` where module="%s"' % (dt,mod))
			for e in dl2:
				dl += [dt + ',' + e[0] + ',0']
				
				if e[0] == 'Control Panel':
					dl += [e[0]+','+e[0]+',1']
		except:
			pass
	dl1 = webnotes.conn.sql('select doctype_list from `tabModule Def` where name=%s', mod)
	dl1 = dl1 and dl1[0][0] or ''
	if dl1:		
		dl1 = dl1.split('\n')
		dl += [t+',1' for t in dl1]
	dl += ['Module Def,'+mod+',0']
	# build finally
	dl = [e.split(',') for e in dl]
	dl = [[e[0].strip(), e[1].strip(), e[2]] for e in dl] # remove blanks
	return dl


# ==============================================================================
# build a list of doclists of items in that module and send them
# ==============================================================================

def get_module_doclist(module):
	import webnotes
	import webnotes.model.doc
	item_list = get_module_items(module)
	
	# build the super_doclist
	super_doclist = []
	for i in item_list:
		dl = webnotes.model.doc.get(i[0], i[1])
		if i[2]=='1':
			dl[0].module = module
		# remove compiled code (if any)
		if dl[0].server_code_compiled:
			dl[0].server_code_compiled = None
			
		# add to super
		super_doclist.append([d.fields for d in dl])
		
	return super_doclist

# ==============================================================================
# Create __init__.py files
# ==============================================================================

def create_init_py(modules_path, dt, dn):
	import os
	from webnotes.modules import scrub
	
	# in module
	if not '__init__.py' in os.listdir(modules_path):
		open(os.path.join(modules_path, '__init__.py'), 'w').close()

	# in type and name folders
	if dt in ['doctype', 'page', 'search_criteria']:
		if not '__init__.py' in os.listdir(os.path.join(modules_path, dt)):
			open(os.path.join(modules_path, dt, '__init__.py'), 'w').close()

		if not '__init__.py' in os.listdir(os.path.join(modules_path, dt, dn)):
			open(os.path.join(modules_path, dt, dn, '__init__.py'), 'w').close()


# ==============================================================================
# Create module folders
# ==============================================================================

def create_folder(module, dt, dn):
	import webnotes, os
	
	# get module path by importing the module
	modules_path = get_module_path(module)
			
	code_type = dt in ['DocType', 'Page', 'Search Criteria']
	
	# create folder
	folder = os.path.join(modules_path, code_type and scrub(dt) or dt, code_type and scrub(dn) or dn)
	
	webnotes.create_folder(folder)
	
	# create init_py_files
	if code_type:
		create_init_py(modules_path, scrub(dt), scrub(dn))
	
	return folder

# ==============================================================================
# Write doclist into file
# ==============================================================================

def write_document_file(doclist, record_module=None):
	import os
	from webnotes.utils import pprint_dict

	global updated_modules

	# module name
	if doclist[0]['doctype'] == 'Module Def':
		module = doclist[0]['name']
	elif doclist[0]['doctype']=='Control Panel':
		module = 'System'
	elif record_module:
		module = record_module
	else:
		module = doclist[0]['module']

	updated_modules.append(module)

	# create the folder
	code_type = doclist[0]['doctype'] in ['DocType','Page','Search Criteria']
	
	# create folder
	folder = create_folder(module, doclist[0]['doctype'], doclist[0]['name'])
	
	# separate code files
	clear_code_fields(doclist, folder, code_type)
		
	# write the data file	
	fname = (code_type and scrub(doclist[0]['name'])) or doclist[0]['name']
	dict_list = [pprint_dict(d) for d in doclist]	
	
	txtfile = open(os.path.join(folder, fname +'.txt'),'w+')	
	txtfile.write('[\n' + ',\n'.join(dict_list) + '\n]')
	txtfile.close()


# ==============================================================================
# Create seperate files for code
# ==============================================================================

def clear_code_fields(doclist, folder, code_type):
	
	import os
	import webnotes
	# code will be in the parent only
	code_fields = webnotes.code_fields_dict.get(doclist[0]['doctype'], [])
	
	for code_field in code_fields:
		if doclist[0].get(code_field[0]):

			doclist[0][code_field[0]] = None
		
