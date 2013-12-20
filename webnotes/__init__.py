# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 
"""
globals attached to webnotes module
+ some utility functions that should probably be moved
"""

from __future__ import unicode_literals

from werkzeug.local import Local
from werkzeug.exceptions import NotFound
from MySQLdb import ProgrammingError as SQLError

import os, sys, importlib
import json
import semantic_version

local = Local()

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
	def copy(self):
		return _dict(dict(self).copy())

def __getattr__(self, key):
	return local.get("key", None)
	
def _(msg):
	"""translate object in current lang, if exists"""
	if local.lang == "en":
		return msg

	from webnotes.translate import get_full_dict
	return get_full_dict(local.lang).get(msg, msg)

def get_lang_dict(fortype, name=None):
	if local.lang=="en":
		return {}
	from webnotes.translate import get_dict
	return get_dict(fortype, name)
	
def set_user_lang(user, user_language=None):
	from webnotes.translate import get_lang_dict
		
	if not user_language:
		user_language = conn.get_value("Profile", user, "language")

	if user_language:
		lang_dict = get_lang_dict()
		if user_language in lang_dict:
			local.lang = lang_dict[user_language]

# local-globals
conn = local("conn")
conf = local("conf")
form = form_dict = local("form_dict")
request = local("request")
request_method = local("request_method")
response = local("response")
_response = local("_response")
session = local("session")
user = local("user")
flags = local("flags")

error_log = local("error_log")
debug_log = local("debug_log")
message_log = local("message_log")

lang = local("lang")
	
def init(site, sites_path=None):
	if getattr(local, "initialised", None):
		return

	if not sites_path:
		sites_path = '.'
			
	local.error_log = []
	local.site = site
	local.sites_path = sites_path
	local.site_path = os.path.join(sites_path, site)
	local.message_log = []
	local.debug_log = []
	local.response = _dict({})
	local.lang = "en"
	local.request_method = request.method if request else None
	local.conf = _dict(get_site_config())
	local.initialised = True
	local.flags = _dict({})
	local.rollback_observers = []
	local.module_app = None
	local.app_modules = None

	setup_module_map()

def get_site_config():
	site_filepath = os.path.join(local.site_path, "site_config.json")
	if os.path.exists(site_filepath):
		with open(site_filepath, 'r') as f:
			return json.load(f)
	else:
		return _dict()

def destroy():
	"""closes connection and releases werkzeug local"""
	if conn:
		conn.close()
	
	from werkzeug.local import release_local
	release_local(local)

_memc = None
test_objects = {}

# memcache
def cache():
	global _memc
	if not _memc:
		from webnotes.memc import MClient
		_memc = MClient(['localhost:11211'])
	return _memc
		
class DuplicateEntryError(Exception): pass
class ValidationError(Exception): pass
class AuthenticationError(Exception): pass
class PermissionError(Exception): pass
class UnknownDomainError(Exception): pass
class SessionStopped(Exception): pass
class MappingMismatchError(ValidationError): pass
class InvalidStatusError(ValidationError): pass
class DoesNotExistError(ValidationError): pass
class MandatoryError(ValidationError): pass
class InvalidSignatureError(ValidationError): pass
		
def get_traceback():
	import utils
	return utils.get_traceback()

def errprint(msg):
	from utils import cstr
	if not request:
		print cstr(msg)

	error_log.append(cstr(msg))

def log(msg):
	if not request:
		import conf
		if conf.get("logging") or False:
			print repr(msg)
	
	from utils import cstr
	debug_log.append(cstr(msg))

def msgprint(msg, small=0, raise_exception=0, as_table=False):
	def _raise_exception():
		if raise_exception:
			if flags.rollback_on_exception:
				conn.rollback()
			import inspect
			if inspect.isclass(raise_exception) and issubclass(raise_exception, Exception):
				raise raise_exception, msg
			else:
				raise ValidationError, msg

	if flags.mute_messages:
		_raise_exception()
		return

	from utils import cstr
	if as_table and type(msg) in (list, tuple):
		msg = '<table border="1px" style="border-collapse: collapse" cellpadding="2px">' + ''.join(['<tr>'+''.join(['<td>%s</td>' % c for c in r])+'</tr>' for r in msg]) + '</table>'
	
	if flags.print_messages:
		print "Message: " + repr(msg)
	
	message_log.append((small and '__small:' or '')+cstr(msg or ''))
	_raise_exception()

def throw(msg, exc=ValidationError):
	msgprint(msg, raise_exception=exc)
	
def create_folder(path):
	if not os.path.exists(path): os.makedirs(path)
			
def connect(site=None, db_name=None):
	from db import Database
	if site:
		init(site)
	local.conn = Database(user=db_name or local.conf.db_name)
	local.response = _dict()
	local.form_dict = _dict()
	local.session = _dict()
	set_user("Administrator")
	
def set_user(username):
	import webnotes.profile
	local.session["user"] = username
	local.user = webnotes.profile.Profile(username)
	
def get_request_header(key, default=None):
	return request.headers.get(key, default)

logger = None
whitelisted = []
guest_methods = []
def whitelist(allow_guest=False, allow_roles=None):
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
	"""clear cache"""
	from webnotes.sessions import clear_cache
	if doctype:
		from webnotes.model.doctype import clear_cache
		clear_cache(doctype)
		reset_metadata_version()
	elif user:
		clear_cache(user)
	else: # everything
		import translate
		clear_cache()
		translate.clear_cache()
		reset_metadata_version()
	
def get_roles(username=None):
	import webnotes.profile
	if not username or username==session.user:
		return user.get_roles()
	else:
		return webnotes.profile.Profile(username).get_roles()

def check_admin_or_system_manager():
	if ("System Manager" not in get_roles()) and \
	 	(session.user!="Administrator"):
		msgprint("Only Allowed for Role System Manager or Administrator", raise_exception=True)

def has_permission(doctype, ptype="read", refdoc=None):
	"""check if user has permission"""
	from webnotes.utils import cint
	
	if session.user=="Administrator" or conn.get_value("DocType", doctype, "istable")==1:
		return True
		
	meta = get_doctype(doctype)
	
	# get user permissions
	user_roles = get_roles()
	perms = [p for p in meta.get({"doctype": "DocPerm"}) 
		if cint(p.get(ptype))==1 and cint(p.permlevel)==0 and (p.role=="All" or p.role in user_roles)]
	
	if refdoc:
		return has_match(meta, perms, refdoc)
	else:
		return perms and True or False
		
def has_match(meta, perms, refdoc):
	from webnotes.defaults import get_user_default_as_list
	
	if isinstance(refdoc, basestring):
		refdoc = doc(meta[0].name, refdoc)
	
	match_failed = {}
	for p in perms:
		if p.match:
			if ":" in p.match:
				keys = p.match.split(":")
			else:
				keys = [p.match, p.match]
			
			if refdoc.fields.get(keys[0],"[No Value]") in get_user_default_as_list(keys[1]):
				return True
			else:
				match_failed[keys[0]] = refdoc.fields.get(keys[0],"[No Value]")
		else:
			# found a permission without a match
			return True

	# no valid permission found
	if match_failed:
		msg = _("Not allowed for: ")
		for key in match_failed:
			msg += "\n" + (meta.get_field(key) and meta.get_label(key) or key) \
				+ " = " + (match_failed[key] or "None")
		msgprint(msg)
	
	return False

def generate_hash():
	"""Generates random hash for session id"""
	import hashlib, time
	return hashlib.sha224(str(time.time())).hexdigest()

def reset_metadata_version():
	v = generate_hash()
	cache().set_value("metadata_version", v)
	return v

def get_obj(dt = None, dn = None, doc=None, doclist=[], with_children = True):
	from webnotes.model.code import get_obj
	return get_obj(dt, dn, doc, doclist, with_children)

def doc(doctype=None, name=None, fielddata=None):
	from webnotes.model.doc import Document
	return Document(doctype, name, fielddata)

def new_doc(doctype, parent_doc=None, parentfield=None):
	from webnotes.model.create_new import get_new_doc
	return get_new_doc(doctype, parent_doc, parentfield)

def new_bean(doctype):
	from webnotes.model.create_new import get_new_doc
	return bean([get_new_doc(doctype)])

def doclist(lst=None):
	from webnotes.model.doclist import DocList
	return DocList(lst)

def bean(doctype=None, name=None, copy=None):
	"""return an instance of the object, wrapped as a Bean (webnotes.model.bean)"""
	from webnotes.model.bean import Bean
	if copy:
		return Bean(copy_doclist(copy))
	else:
		return Bean(doctype, name)

def set_value(doctype, docname, fieldname, value):
	import webnotes.client
	return webnotes.client.set_value(doctype, docname, fieldname, value)

def get_doclist(doctype, name=None):
	return bean(doctype, name).doclist
	
def get_doctype(doctype, processed=False):
	import webnotes.model.doctype
	return webnotes.model.doctype.get(doctype, processed)

def delete_doc(doctype=None, name=None, doclist = None, force=0, ignore_doctypes=None, for_reload=False, ignore_permissions=False):
	import webnotes.model.utils

	if not ignore_doctypes: 
		ignore_doctypes = []
	
	if isinstance(name, list):
		for n in name:
			webnotes.model.utils.delete_doc(doctype, n, doclist, force, ignore_doctypes, for_reload, ignore_permissions)
	else:
		webnotes.model.utils.delete_doc(doctype, name, doclist, force, ignore_doctypes, for_reload, ignore_permissions)

def clear_perms(doctype):
	conn.sql("""delete from tabDocPerm where parent=%s""", doctype)

def reset_perms(doctype):
	clear_perms(doctype)
	reload_doc(conn.get_value("DocType", doctype, "module"), "DocType", doctype, force=True)

def reload_doc(module, dt=None, dn=None, force=False):
	import webnotes.modules
	return webnotes.modules.reload_doc(module, dt, dn, force=force)

def rename_doc(doctype, old, new, debug=0, force=False, merge=False):
	from webnotes.model.rename_doc import rename_doc
	return rename_doc(doctype, old, new, force=force, merge=merge)

def insert(doclist):
	import webnotes.model
	return webnotes.model.insert(doclist)

def get_module(modulename):
	return importlib.import_module(modulename)

def scrub(txt):
	return txt.replace(' ','_').replace('-', '_').replace('/', '_').lower()

def get_module_path(module, *joins):
	module = scrub(module)
	return get_pymodule_path(local.module_app[module] + "." + module, *joins)
	
def get_pymodule_path(modulename, *joins):
	joins = [scrub(part) for part in joins]
	return os.path.join(os.path.dirname(get_module(scrub(modulename)).__file__), *joins)
	
def get_module_list(app_name):
	return get_file_items(os.path.join(os.path.dirname(get_module(app_name).__file__), "modules.txt"))

def get_all_apps(with_webnotes=False):
	apps = get_file_items(os.path.join(local.sites_path, "apps.txt"))
	if with_webnotes:
		apps.insert(0, 'webnotes')
	return apps

def get_installed_apps():
	if flags.in_install_db:
		return []
	def load_installed_apps():
		return json.loads(conn.get_global("installed_apps") or "[]")
	return cache().get_value("installed_apps", load_installed_apps)

def get_hooks(app_name=None):
	def load_app_hooks(app_name=None):
		hooks = {}
		for app in [app_name] if app_name else get_installed_apps():
			for item in get_file_items(get_pymodule_path(app, "hooks.txt")):
				key, value = item.split(None, 1)
				hooks.setdefault(key, [])
				hooks[key].append(value)
		return hooks
	if app_name:
		return _dict(load_app_hooks(app_name=None))
	else:
		return _dict(cache().get_value("app_hooks", load_app_hooks))

def setup_module_map():
	_cache = cache()
	
	if conf.db_name:
		local.app_modules = _cache.get_value("app_modules")
		local.module_app = _cache.get_value("module_app")
	
	if not local.app_modules:
		local.module_app, local.app_modules = {}, {}
		for app in get_all_apps(True):
			for module in get_module_list(app):
				local.module_app[module] = app
				local.app_modules.setdefault(app, [])
				local.app_modules[app].append(module)
	
		if conf.db_name:
			_cache.set_value("app_modules", local.app_modules)
			_cache.set_value("module_app", local.module_app)
		
def get_file_items(path):
	if os.path.exists(path):
		with open(path, "r") as f: 
			content = unicode(f.read(), encoding="utf-8")
		return [p.strip() for p in content.splitlines() if p.strip() and not p.startswith("#")]
	else: 
		return []

def get_attr(method_string):
	modulename = '.'.join(method_string.split('.')[:-1])
	methodname = method_string.split('.')[-1]

	return getattr(get_module(modulename), methodname)
	
def make_property_setter(args):
	args = _dict(args)
	bean([{
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
		return conn.get_value("Control Panel", None, "home_page")

def copy_doclist(in_doclist):
	new_doclist = []
	parent_doc = None
	for i, d in enumerate(in_doclist):
		is_dict = False
		if isinstance(d, dict):
			is_dict = True
			values = _dict(d.copy())
		else:
			values = _dict(d.fields.copy())
		
		newd = new_doc(values.doctype, parent_doc=(None if i==0 else parent_doc), parentfield=values.parentfield)
		newd.fields.update(values)
		
		if i==0:
			parent_doc = newd
		
		new_doclist.append(newd.fields if is_dict else newd)

	return doclist(new_doclist)

def compare(val1, condition, val2):
	import webnotes.utils
	return webnotes.utils.compare(val1, condition, val2)
	
def repsond_as_web_page(title, html):
	local.message_title = title
	local.message = "<h3>" + title + "</h3>" + html
	local.response['type'] = 'page'
	local.response['page_name'] = 'message.html'
	
def build_match_conditions(doctype, fields=None, as_condition=True):
	import webnotes.widgets.reportview
	return webnotes.widgets.reportview.build_match_conditions(doctype, fields, as_condition)

def get_list(doctype, filters=None, fields=None, docstatus=None, 
			group_by=None, order_by=None, limit_start=0, limit_page_length=None, 
			as_list=False, debug=False):
	import webnotes.widgets.reportview
	return webnotes.widgets.reportview.execute(doctype, filters=filters, fields=fields, docstatus=docstatus, 
				group_by=group_by, order_by=order_by, limit_start=limit_start, limit_page_length=limit_page_length, 
				as_list=as_list, debug=debug)

jenv = None

def get_jenv():
	global jenv
	if not jenv:
		from jinja2 import Environment, ChoiceLoader, PackageLoader
		from webnotes.utils import get_base_path, global_date_format
		from markdown2 import markdown
		from json import dumps

		# webnotes will be loaded last, so app templates will get precedence
		jenv = Environment(loader = ChoiceLoader([PackageLoader(app, ".") \
			for app in get_all_apps() + ["webnotes"]]))

		jenv.filters["global_date_format"] = global_date_format
		jenv.filters["markdown"] = markdown
		jenv.filters["json"] = dumps
	
	return jenv

def get_template(path):
	return get_jenv().get_template(path)
