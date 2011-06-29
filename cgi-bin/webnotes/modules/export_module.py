from webnotes.modules import scrub, get_module_path

def export_to_files(record_list=[], record_module=None, verbose=0):
	module_doclist =[]
	if record_list:
		for record in record_list:
			doclist = [d.fields for d in webnotes.model.doc.get(record[0], record[1])]
			write_document_file(doclist, record_module)

	return out

def create_init_py(modules_path, module, dt, dn):
	import os
	from webnotes.modules import scrub
	
	def create_if_not_exists(path):
		initpy = os.path.join(path, '__init__.py')
		if not os.path.exists(initpy):
			open(initpy, 'w').close()
	
	create_if_not_exists(os.path.join(modules_path, module))
	create_if_not_exists(os.path.join(modules_path, module, dt))
	create_if_not_exists(os.path.join(modules_path, module, dt, dn))
	
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
		create_init_py(modules_path, module, scrub(dt), scrub(dn))
	
	return folder

def get_module_name(doclist, record_module=None):
	# module name
	if doclist[0]['doctype'] == 'Module Def':
		module = doclist[0]['name']
	elif doclist[0]['doctype']=='Control Panel':
		module = 'Core'
	elif record_module:
		module = record_module
	else:
		module = doclist[0]['module']

	return module
	
def write_document_file(doclist, record_module=None):
	import os
	from webnotes.utils import pprint_dict

	module = get_module_name()

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

def clear_code_fields(doclist, folder, code_type):
	
	import os
	import webnotes
	# code will be in the parent only
	code_fields = webnotes.code_fields_dict.get(doclist[0]['doctype'], [])
	
	for code_field in code_fields:
		if doclist[0].get(code_field[0]):

			doclist[0][code_field[0]] = None
		
