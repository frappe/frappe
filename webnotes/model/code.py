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

import webnotes
from webnotes.modules import get_doctype_module
import webnotes.model.doc

def get_obj(dt = None, dn = None, doc=None, doclist=[], with_children = 0):
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

def get_server_obj(doc, doclist = [], basedoctype = ''):
	# for test
	module = get_doctype_module(doc.doctype)
	return load_doctype_module(doc.doctype, module).DocType(doc, doclist)

def load_doctype_module(doctype, module=None, prefix=""):
	if not module:
		module = get_doctype_module(doctype)
	return webnotes.get_module(get_module_name(doctype, module, prefix))
	
def get_module_name(doctype, module, prefix=""):
	from webnotes.modules import scrub
	return '{app}.{module}.doctype.{doctype}.{prefix}{doctype}'.format(\
		app = scrub(webnotes.local.module_app[scrub(module)]), 
		module = scrub(module), doctype = scrub(doctype), prefix=prefix)

		
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