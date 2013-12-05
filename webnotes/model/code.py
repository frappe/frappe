# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
This is where all the plug-in code is executed. The standard method for DocTypes is declaration of a 
standardized `DocType` class that has the methods of any DocType. When an object is instantiated using the
`get_obj` method, it creates an instance of the `DocType` class of that particular DocType and sets the 
`doc` and `doclist` attributes that represent the fields (properties) of that record.

methods in following modules are imported for backward compatibility

	* webnotes.*
	* webnotes.utils.*
	* webnotes.model.doc.*
	* webnotes.model.bean.*
"""
def get_server_obj(doc, doclist = [], basedoctype = ''):
	# for test
	import webnotes
	from webnotes.modules import scrub, get_doctype_module
	from webnotes.plugins import get_code_and_execute

	# get doctype details
	module = get_doctype_module(doc.doctype) or "core"
		
	if not module:
		return
		
	DocType = get_doctype_class(doc.doctype, module)
	
	if webnotes.flags.in_import:
		return DocType(doc, doclist)

	# custom?
	namespace = {"DocType": DocType}
	get_code_and_execute(module, "DocType", doc.doctype, namespace=namespace)
	if namespace.get("CustomDocType"):
		return namespace["CustomDocType"](doc, doclist)
	else:
		return DocType(doc, doclist)

def get_doctype_class(doctype, module):
	from webnotes.utils import cint
	import webnotes

	module = load_doctype_module(doctype, module)
	if module:
		DocType = getattr(module, 'DocType')
	else:
		if not cint(webnotes.conn.get_value("DocType", doctype, "custom")):
			raise ImportError, "Unable to load module for: " + doctype
		
		class DocType:
			def __init__(self, d, dl):
				self.doc, self.doclist = d, dl

	return DocType

def get_module_name(doctype, module, prefix):
	from webnotes.modules import scrub
	_doctype, _module = scrub(doctype), scrub(module)
	return '%s.doctype.%s.%s%s' % (_module, _doctype, prefix, _doctype)

def load_doctype_module(doctype, module=None, prefix=""):
	import webnotes
	from webnotes.modules import scrub, get_doctype_module
	if not module:
		module = get_doctype_module(doctype) or "core"
	try:
		module = __import__(get_module_name(doctype, module, prefix), fromlist=[''])
		return module
	except ImportError, e:
		# webnotes.errprint(webnotes.getTraceback())
		return None

def get_obj(dt = None, dn = None, doc=None, doclist=[], with_children = 0):
	import webnotes.model.doc
	if dt:
		if isinstance(dt, list):
			return get_server_obj(dt[0], dt)
		if isinstance(dt, webnotes.model.doc.Document):
			return get_server_obj(dt, [dt])
		if not dn:
			dn = dt
		if with_children:
			doclist = webnotes.model.doc.get(dt, dn, from_controller=1)
		else:
			doclist = webnotes.model.doc.get(dt, dn, with_children = 0, from_controller=1)
		return get_server_obj(doclist[0], doclist)
	else:
		return get_server_obj(doc, doclist)
		
def run_server_obj(server_obj, method_name, arg=None):
	"""
	   Executes a method (`method_name`) from the given object (`server_obj`)
	"""
	if server_obj and hasattr(server_obj, method_name):
		if arg:
			return getattr(server_obj, method_name)(arg)
		else:
			return getattr(server_obj, method_name)()
	else:
		raise Exception, 'No method %s' % method_name

def get_code(module, dt, dn, extn, fieldname=None):
	from webnotes.modules import scrub, get_module_path
	import os, webnotes
	
	# get module (if required)
	if not module:
		module = webnotes.conn.get_value(dt, dn, 'module')

	# no module, quit
	if not module:
		return ''
	
	# file names
	if dt in ('Page','Doctype'):
		dt, dn = scrub(dt), scrub(dn)

	# get file name
	fname = dn + '.' + extn

	# code
	code = ''
	try:
		file = open(os.path.join(get_module_path(scrub(module)), dt, dn, fname), 'r')
		code = file.read()
		file.close()	
	except IOError, e:
		# no file, try from db
		if fieldname:
			code = webnotes.conn.get_value(dt, dn, fieldname)

	return code
