# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals

import webnotes, os
import webnotes.model.doc
from webnotes.modules import scrub, get_module_path, lower_case_files_for, \
	code_fields_dict, scrub_dt_dn

def export_doc(doc):
	export_to_files([[doc.doctype, doc.name]])

def export_to_files(record_list=[], record_module=None, verbose=0):
	"""
		Export record_list to files. record_list is a list of lists ([doctype],[docname] )  ,
	"""
	from webnotes.modules.import_merge import in_transfer
	if in_transfer:
		return
			
	module_doclist =[]
	if record_list:
		for record in record_list:
			write_document_file(webnotes.model.doc.get(record[0], record[1]), 
				record_module)
	
def write_document_file(doclist, record_module=None):
	from webnotes.modules.utils import pprint_doclist

	doclist = [filter_fields(d.fields) for d in doclist]

	module = record_module or get_module_name(doclist)
	code_type = doclist[0]['doctype'] in lower_case_files_for
	
	# create folder
	folder = create_folder(module, doclist[0]['doctype'], doclist[0]['name'], code_type)
	
	# separate code files
	clear_code_fields(doclist, folder, code_type)
		
	# write the data file	
	fname = (code_type and scrub(doclist[0]['name'])) or doclist[0]['name']
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
		
def create_folder(module, dt, dn, code_type):
	# get module path by importing the module
	module_path = get_module_path(module)

	dt, dn = scrub_dt_dn(dt, dn)
	
	# create folder
	folder = os.path.join(module_path, dt, dn)
	
	webnotes.create_folder(folder)
	
	# create init_py_files
	if code_type:
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


def clear_code_fields(doclist, folder, code_type):
	code_fields = code_fields_dict.get(doclist[0]['doctype'], [])
	for code_field in code_fields:
		if doclist[0].get(code_field[0]):
			doclist[0][code_field[0]] = None

