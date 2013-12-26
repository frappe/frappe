# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes, os
import webnotes.model.doc
from webnotes.modules import scrub, get_module_path, lower_case_files_for, scrub_dt_dn

def export_doc(doc):
	export_to_files([[doc.doctype, doc.name]])

def export_to_files(record_list=None, record_module=None, verbose=0, create_init=None):
	"""
		Export record_list to files. record_list is a list of lists ([doctype],[docname] )  ,
	"""
	if webnotes.flags.in_import:
		return

	module_doclist =[]
	if record_list:
		for record in record_list:
			write_document_file(webnotes.model.doc.get(record[0], record[1]), 
				record_module, create_init=create_init)
	
def write_document_file(doclist, record_module=None, create_init=None):
	from webnotes.modules.utils import pprint_doclist

	doclist = [filter_fields(d.fields) for d in doclist]

	module = record_module or get_module_name(doclist)
	if create_init is None:
		create_init = doclist[0]['doctype'] in lower_case_files_for
	
	# create folder
	folder = create_folder(module, doclist[0]['doctype'], doclist[0]['name'], create_init)
	
	# write the data file	
	fname = (doclist[0]['doctype'] in lower_case_files_for and scrub(doclist[0]['name'])) or doclist[0]['name']
	with open(os.path.join(folder, fname +'.txt'),'w+') as txtfile:
		txtfile.write(pprint_doclist(doclist))

def filter_fields(doc):
	from webnotes.model.doctype import get
	from webnotes.model import default_fields

	doctypelist = get(doc.doctype, False)
	valid_fields = [d.fieldname for d in doctypelist.get({"parent":doc.doctype,
		"doctype":"DocField"})]
	to_remove = []
	
	for key in doc:
		if (not key in default_fields) and (not key in valid_fields):
			to_remove.append(key)
		elif doc[key]==None:
			to_remove.append(key)
			
	for key in to_remove:
		del doc[key]
	
	return doc

def get_module_name(doclist):
	if doclist[0]['doctype'] == 'Module Def':
		module = doclist[0]['name']
	elif doclist[0]['doctype']=='Control Panel':
		module = 'Core'
	elif doclist[0]['doctype']=="Workflow":
		module = webnotes.conn.get_value("DocType", doclist[0]["document_type"], "module")
	else:
		module = doclist[0]['module']

	return module
		
def create_folder(module, dt, dn, create_init):
	module_path = get_module_path(module)

	dt, dn = scrub_dt_dn(dt, dn)
	
	# create folder
	folder = os.path.join(module_path, dt, dn)
	
	webnotes.create_folder(folder)
	
	# create init_py_files
	if create_init:
		create_init_py(module_path, dt, dn)
	
	return folder

def create_init_py(module_path, dt, dn):
	def create_if_not_exists(path):
		initpy = os.path.join(path, '__init__.py')
		if not os.path.exists(initpy):
			open(initpy, 'w').close()
	
	create_if_not_exists(os.path.join(module_path))
	create_if_not_exists(os.path.join(module_path, dt))
	create_if_not_exists(os.path.join(module_path, dt, dn))
