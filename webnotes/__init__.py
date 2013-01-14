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
"""
globals attached to webnotes module
+ some utility functions that should probably be moved
"""

code_fields_dict = {
	'Page':[('script', 'js'), ('content', 'html'), ('style', 'css'), ('static_content', 'html'), ('server_code', 'py')],
	'DocType':[('server_code_core', 'py'), ('client_script_core', 'js')],
	'Search Criteria':[('report_script', 'js'), ('server_script', 'py'), ('custom_query', 'sql')],
	'Patch':[('patch_code', 'py')],
	'Stylesheet':['stylesheet', 'css'],
	'Page Template':['template', 'html'],
	'Control Panel':[('startup_code', 'js'), ('startup_css', 'css')]
}

class _dict(dict):
	"""dict like object that exposes keys as attributes"""
	def __getattr__(self, key):
		return self.get(key)
	def __setattr__(self, key, value):
		self[key] = value
	def __getstate__(self): 
		return self
	def __setstate__(self, d): 
		self.update(d)
	def update(self, d):
		"""update and return self -- the missing dict feature in python"""
		super(_dict, self).update(d)
		return self
		
def _(msg):
	"""translate object in current lang, if exists"""
	from webnotes.translate import messages
	return messages.get(lang, {}).get(msg, msg)

request = form_dict = _dict()
conn = None
_memc = None
form = None
session = None
user = None
incoming_cookies = {}
add_cookies = {} # append these to outgoing request
cookies = {}
response = _dict({'message':'', 'exc':''})
debug_log = []
message_log = []
lang = 'en'

# memcache

def cache():
	global _memc
	if not _memc:
		from webnotes.memc import MClient
		_memc = MClient(['localhost:11211'])
	return _memc
		
class ValidationError(Exception):
	pass
	
class AuthenticationError(Exception):
	pass

class PermissionError(Exception):
	pass
	
class OutgoingEmailError(ValidationError):
	pass

class UnknownDomainError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)	

class SessionStopped(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)	
		
def getTraceback():
	import utils
	return utils.getTraceback()

def errprint(msg):
	"""
	   Append to the :data:`debug log`
	"""
	from utils import cstr
	debug_log.append(cstr(msg or ''))

def msgprint(msg, small=0, raise_exception=0, as_table=False):
	"""
	   Append to the :data:`message_log`
	"""	
	from utils import cstr
	if as_table and type(msg) in (list, tuple):
		msg = '<table border="1px" style="border-collapse: collapse" cellpadding="2px">' + ''.join(['<tr>'+''.join(['<td>%s</td>' % c for c in r])+'</tr>' for r in msg]) + '</table>'
	
	message_log.append((small and '__small:' or '')+cstr(msg or ''))
	if raise_exception:
		import inspect
		if inspect.isclass(raise_exception) and issubclass(raise_exception, Exception):
			raise raise_exception, msg
		else:
			raise ValidationError, msg
	
def create_folder(path):
	"""
	Wrapper function for os.makedirs (does not throw exception if directory exists)
	"""
	import os
	
	try:
		os.makedirs(path)
	except OSError, e:
		if e.args[0]!=17: 
			raise e

def create_symlink(source_path, link_path):
	"""
	Wrapper function for os.symlink (does not throw exception if directory exists)
	"""
	import os
	
	try:
		os.symlink(source_path, link_path)
	except OSError, e:
		if e.args[0]!=17: 
			raise e

def remove_file(path):
	"""
	Wrapper function for os.remove (does not throw exception if file/symlink does not exists)
	"""
	import os
	
	try:
		os.remove(path)
	except OSError, e:
		if e.args[0]!=2: 
			raise e
			
def connect(db_name=None, password=None):
	"""
		Connect to this db (or db), if called from command prompt
	"""
	import webnotes.db
	global conn
	conn = webnotes.db.Database(user=db_name, password=password)
	
	global session
	session = _dict({'user':'Administrator'})
	
	import webnotes.profile
	global user
	user = webnotes.profile.Profile('Administrator')	

def get_env_vars(env_var):
	import os
	return os.environ.get(env_var,'None')

remote_ip = get_env_vars('REMOTE_ADDR')		#Required for login from python shell
logger = None
	
def get_db_password(db_name):
	"""get db password from conf"""
	import conf
	
	if hasattr(conf, 'get_db_password'):
		return conf.get_db_password(db_name)
		
	elif hasattr(conf, 'db_password'):
		return conf.db_password
		
	else:
		return db_name


whitelisted = []
guest_methods = []
def whitelist(allow_guest=False, allow_roles=[]):
	"""
	decorator for whitelisting a function
	
	Note: if the function is allowed to be accessed by a guest user,
	it must explicitly be marked as allow_guest=True
	
	for specific roles, set allow_roles = ['Administrator'] etc.
	"""
	def innerfn(fn):
		global whitelisted, guest_methods
		whitelisted.append(fn)

		if allow_guest:
			guest_methods.append(fn)

		if allow_roles:
			roles = get_roles()
			allowed = False
			for role in allow_roles:
				if role in roles:
					allowed = True
					break
			
			if not allowed:
				raise PermissionError, "Method not allowed"

		return fn

	return innerfn
	
def clear_cache(user=None, doctype=None):
	"""clear boot cache"""
	if doctype:
		from webnotes.model.doctype import clear_cache
		clear_cache(doctype)
	else:
		from webnotes.sessions import clear
		clear(user)
	
def get_roles(user=None, with_standard=True):
	"""get roles of current user"""
	if not user:
		user = session.user

	if user=='Guest':
		return ['Guest']
		
	roles = [r[0] for r in conn.sql("""select role from tabUserRole 
		where parent=%s and role!='All'""", user)] + ['All']
		
	# filter standard if required
	if not with_standard:
		roles = filter(lambda x: x not in ['All', 'Guest', 'Administrator'], roles)
	
	return roles

def has_permission(doctype, ptype="read"):
	"""check if user has permission"""
	if session.user=="Administrator": 
		return True
	if conn.get_value("DocType", doctype, "istable"):
		return True
	return conn.sql("""select name from tabDocPerm p
		where p.parent = %s
		and ifnull(p.`%s`,0) = 1
		and ifnull(p.permlevel,0) = 0
		and (p.role="All" or p.role in (select `role` from tabUserRole where `parent`=%s))
		""" % ("%s", ptype, "%s"), (doctype, session.user))

def generate_hash():
	"""Generates random hash for session id"""
	import hashlib, time
	return hashlib.sha224(str(time.time())).hexdigest()

def get_obj(dt = None, dn = None, doc=None, doclist=[], with_children = 0):
	from webnotes.model.code import get_obj
	return get_obj(dt, dn, doc, doclist, with_children)

def doc(doctype=None, name=None, fielddata=None):
	from webnotes.model.doc import Document
	return Document(doctype, name, fielddata)

def doclist(lst=None):
	from webnotes.model.doclist import DocList
	return DocList(lst)

def model_wrapper(doctype=None, name=None):
	from webnotes.model.wrapper import ModelWrapper
	return ModelWrapper(doctype, name)

def get_doclist(doctype, name=None):
	return model_wrapper(doctype, name).doclist
	
def get_doctype(doctype, processed=False):
	import webnotes.model.doctype
	return webnotes.model.doctype.get(doctype, processed)

def delete_doc(doctype=None, name=None, doclist = None, force=0):
	import webnotes.model
	webnotes.model.delete_doc(doctype, name, doclist, force)

def clear_perms(doctype):
	conn.sql("""delete from tabDocPerm where parent=%s""", doctype)

def reset_perms(doctype):
	clear_perms(doctype)
	reload_doc(conn.get_value("DocType", doctype, "module"), "DocType", doctype)

def reload_doc(module, dt=None, dn=None):
	import webnotes.modules
	return webnotes.modules.reload_doc(module, dt, dn)

def rename_doc(doctype, old, new, is_doctype=0, debug=0):
	from webnotes.model.rename_doc import rename_doc
	rename_doc(doctype, old, new, is_doctype, debug)

def insert(doclist):
	import webnotes.model
	return webnotes.model.insert(doclist)

def get_method(method_string):
	modulename = '.'.join(method_string.split('.')[:-1])
	methodname = method_string.split('.')[-1]

	__import__(modulename)
	import sys
	moduleobj = sys.modules[modulename]
	return getattr(moduleobj, methodname)
	
def make_property_setter(args):
	args = _dict(args)
	model_wrapper([{
		'doctype': "Property Setter",
		'doctype_or_field': args.doctype_or_field or "DocField",
		'doc_type': args.doctype,
		'field_name': args.fieldname,
		'property': args.property,
		'value': args.value,
		'property_type': args.property_type or "Data",
		'__islocal': 1
	}]).save()

def get_application_home_page(user='Guest'):
	"""get home page for user"""
	hpl = conn.sql("""select home_page 
		from `tabDefault Home Page`
		where parent='Control Panel' 
		and role in ('%s') order by idx asc limit 1""" % "', '".join(get_roles(user)))
	if hpl:
		return hpl[0][0]
	else:
		return conn.get_value('Control Panel',None,'home_page') or 'Login Page'	