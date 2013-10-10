# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
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
custom_class = '''
import webnotes

from webnotes.utils import cint, cstr, flt
from webnotes.model.doc import Document
from webnotes.model.code import get_obj
from webnotes import msgprint

class CustomDocType(DocType):
  def __init__(self, doc, doclist):
    DocType.__init__(self, doc, doclist)
'''


def execute(code, doc=None, doclist=[]):
	# functions used in server script of DocTypes
	# --------------------------------------------------	
	from webnotes.utils import add_days, add_months, add_years, cint, cstr, date_diff, default_fields, flt, fmt_money, formatdate, getTraceback, get_defaults, get_first_day, get_last_day, getdate, has_common, now, nowdate, set_default, user_format, validate_email_add
	from webnotes.utils.email_lib import sendmail
	from webnotes.model import db_exists
	from webnotes.model.doc import Document, addchild, getchildren
	from webnotes.model.utils import getlist
	from webnotes import session, form, msgprint, errprint

	import webnotes

	sql = webnotes.conn.sql
	get_value = webnotes.conn.get_value
	convert_to_lists = webnotes.conn.convert_to_lists
	
	if webnotes.user:
		get_roles = webnotes.user.get_roles
	locals().update({'get_obj':get_obj, 'get_server_obj':get_server_obj, 'run_server_obj':run_server_obj})

	exec code in locals()
	
	if doc:
		d = DocType(doc, doclist)
		return d
		
	if locals().get('page_html'):
		return page_html

	if locals().get('out'):
		return out
		
def get_server_obj(doc, doclist = [], basedoctype = ''):
	# for test
	import webnotes
	from webnotes.modules import scrub, get_doctype_module
	from core.doctype.custom_script.custom_script import get_custom_server_script

	# get doctype details
	module = get_doctype_module(doc.doctype) or "core"
		
	if not module:
		return
		
	DocType = get_doctype_class(doc.doctype, module)

	# custom?
	custom_script = get_custom_server_script(doc.doctype)
		
	if custom_script:
		global custom_class
				
		exec custom_class + '\n' + custom_script.replace('\t','  ') in locals()
			
		return CustomDocType(doc, doclist)
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

def load_doctype_module(doctype, module, prefix=""):
	import webnotes
	from webnotes.modules import scrub
	try:
		module = __import__(get_module_name(doctype, module, prefix), fromlist=[''])
		return module
	except ImportError, e:
		# webnotes.errprint(webnotes.getTraceback())
		return None

def get_obj(dt = None, dn = None, doc=None, doclist=[], with_children = 0):
	if dt:
		import webnotes.model.doc
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
