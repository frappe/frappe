# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
"""
globals attached to frappe module
+ some utility functions that should probably be moved
"""

from __future__ import unicode_literals

from werkzeug.local import Local, release_local
from werkzeug.exceptions import NotFound
from MySQLdb import ProgrammingError as SQLError

import os, sys, importlib, inspect
import json

from .exceptions import *

__version__ = "4.0.0"

local = Local()

class _dict(dict):
	"""dict like object that exposes keys as attributes"""
	def __getattr__(self, key):
		ret = self.get(key)
		if not ret and key.startswith("__"):
			raise AttributeError()
		return ret
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

def _(msg):
	"""translate object in current lang, if exists"""
	if local.lang == "en":
		return msg

	from frappe.translate import get_full_dict
	return get_full_dict(local.lang).get(msg, msg)

def get_lang_dict(fortype, name=None):
	if local.lang=="en":
		return {}
	from frappe.translate import get_dict
	return get_dict(fortype, name)

def set_user_lang(user, user_language=None):
	from frappe.translate import get_user_lang
	local.lang = get_user_lang(user)

# local-globals
db = local("db")
conf = local("conf")
form = form_dict = local("form_dict")
request = local("request")
request_method = local("request_method")
response = local("response")
session = local("session")
user = local("user")
flags = local("flags")
restrictions = local("restrictions")

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
	local.request_method = request.method if request else None
	local.response = _dict({"docs":[]})
	local.conf = _dict(get_site_config())
	local.lang = local.conf.lang or "en"
	local.initialised = True
	local.flags = _dict({})
	local.rollback_observers = []
	local.module_app = None
	local.app_modules = None
	local.user = None
	local.restrictions = None
	local.user_perms = {}
	local.test_objects = {}
	local.jenv = None
	local.jloader =None
	local.cache = {}

	setup_module_map()

def connect(site=None, db_name=None):
	from database import Database
	if site:
		init(site)
	local.db = Database(user=db_name or local.conf.db_name)
	local.form_dict = _dict()
	local.session = _dict()
	set_user("Administrator")

def get_site_config(sites_path=None, site_path=None):
	config = {}

	sites_path = sites_path or getattr(local, "sites_path", None)
	site_path = site_path or getattr(local, "site_path", None)

	if sites_path:
		common_site_config = os.path.join(sites_path, "common_site_config.json")
		if os.path.exists(common_site_config):
			config.update(get_file_json(common_site_config))

	if site_path:
		site_config = os.path.join(site_path, "site_config.json")
		if os.path.exists(site_config):
			config.update(get_file_json(site_config))

	return _dict(config)

def destroy():
	"""closes connection and releases werkzeug local"""
	if db:
		db.close()

	release_local(local)

_memc = None

# memcache
def cache():
	global _memc
	if not _memc:
		from frappe.memc import MClient
		_memc = MClient(['localhost:11211'])
	return _memc

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
		if conf.get("logging") or False:
			print repr(msg)

	from utils import cstr
	debug_log.append(cstr(msg))

def msgprint(msg, small=0, raise_exception=0, as_table=False):
	def _raise_exception():
		if raise_exception:
			if flags.rollback_on_exception:
				db.rollback()
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

def set_user(username):
	from frappe.utils.user import User
	local.session.user = username
	local.session.sid = username
	local.cache = {}
	local.session.data = {}
	local.user = User(username)
	local.restrictions = None
	local.user_perms = {}

def get_request_header(key, default=None):
	return request.headers.get(key, default)

def sendmail(recipients=(), sender="", subject="No Subject", message="No Message", as_markdown=False):
	import frappe.utils.email_lib
	if as_markdown:
		frappe.utils.email_lib.sendmail_md(recipients, sender=sender, subject=subject, msg=message)
	else:
		frappe.utils.email_lib.sendmail(recipients, sender=sender, subject=subject, msg=message)

logger = None
whitelisted = []
guest_methods = []
def whitelist(allow_guest=False):
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

		return fn

	return innerfn

def only_for(roles):
	if not isinstance(roles, (tuple, list)):
		roles = (roles,)
	roles = set(roles)
	myroles = set(get_roles())
	if not roles.intersection(myroles):
		raise PermissionError

def clear_cache(user=None, doctype=None):
	"""clear cache"""
	import frappe.sessions
	if doctype:
		import frappe.model.meta
		frappe.model.meta.clear_cache(doctype)
		reset_metadata_version()
	elif user:
		frappe.sessions.clear_cache(user)
	else: # everything
		import translate
		frappe.sessions.clear_cache()
		translate.clear_cache()
		reset_metadata_version()

def get_roles(username=None):
	from frappe.utils.user import User
	if not local.session:
		return ["Guest"]
	elif not username or username==local.session.user:
		return local.user.get_roles()
	else:
		return User(username).get_roles()

def has_permission(doctype, ptype="read", doc=None):
	import frappe.permissions
	return frappe.permissions.has_permission(doctype, ptype, doc)

def is_table(doctype):
	tables = cache().get_value("is_table")
	if tables==None:
		tables = db.sql_list("select name from tabDocType where ifnull(istable,0)=1")
		cache().set_value("is_table", tables)
	return doctype in tables

def clear_perms(doctype):
	db.sql("""delete from tabDocPerm where parent=%s""", doctype)

def reset_perms(doctype):
	clear_perms(doctype)
	reload_doc(db.get_value("DocType", doctype, "module"),
		"DocType", doctype, force=True)

def generate_hash(txt=None):
	"""Generates random hash for session id"""
	import hashlib, time
	return hashlib.sha224((txt or "") + repr(time.time())).hexdigest()

def reset_metadata_version():
	v = generate_hash()
	cache().set_value("metadata_version", v)
	return v

def new_doc(doctype, parent_doc=None, parentfield=None):
	from frappe.model.create_new import get_new_doc
	return get_new_doc(doctype, parent_doc, parentfield)

def set_value(doctype, docname, fieldname, value):
	import frappe.client
	return frappe.client.set_value(doctype, docname, fieldname, value)

def get_doc(arg1, arg2=None):
	import frappe.model.document
	return frappe.model.document.get_doc(arg1, arg2)

def get_meta(doctype, cached=True):
	import frappe.model.meta
	return frappe.model.meta.get_meta(doctype, cached=cached)

def delete_doc(doctype=None, name=None, force=0, ignore_doctypes=None, for_reload=False, ignore_permissions=False):
	import frappe.model.delete_doc

	if not ignore_doctypes:
		ignore_doctypes = []

	if isinstance(name, list):
		for n in name:
			frappe.model.delete_doc.delete_doc(doctype, n, force, ignore_doctypes, for_reload, ignore_permissions)
	else:
		frappe.model.delete_doc.delete_doc(doctype, name, force, ignore_doctypes, for_reload, ignore_permissions)

def delete_doc_if_exists(doctype, name):
	if db.exists(doctype, name):
		delete_doc(doctype, name)

def reload_doc(module, dt=None, dn=None, force=False):
	import frappe.modules
	return frappe.modules.reload_doc(module, dt, dn, force=force)

def rename_doc(doctype, old, new, debug=0, force=False, merge=False, ignore_permissions=False):
	from frappe.model.rename_doc import rename_doc
	return rename_doc(doctype, old, new, force=force, merge=merge, ignore_permissions=ignore_permissions)

def insert(doclist):
	import frappe.model
	return frappe.model.insert(doclist)

def get_module(modulename):
	return importlib.import_module(modulename)

def scrub(txt):
	return txt.replace(' ','_').replace('-', '_').replace('/', '_').lower()

def unscrub(txt):
	return txt.replace('_',' ').replace('-', ' ').title()

def get_module_path(module, *joins):
	module = scrub(module)
	return get_pymodule_path(local.module_app[module] + "." + module, *joins)

def get_app_path(app_name, *joins):
	return get_pymodule_path(app_name, *joins)

def get_site_path(*joins):
	return os.path.join(local.site_path, *joins)

def get_pymodule_path(modulename, *joins):
	joins = [scrub(part) for part in joins]
	return os.path.join(os.path.dirname(get_module(scrub(modulename)).__file__), *joins)

def get_module_list(app_name):
	return get_file_items(os.path.join(os.path.dirname(get_module(app_name).__file__), "modules.txt"))

def get_all_apps(with_frappe=False, with_internal_apps=True, sites_path=None):
	if not sites_path:
		sites_path = local.sites_path

	apps = get_file_items(os.path.join(sites_path, "apps.txt"), raise_not_found=True)
	if with_internal_apps:
		apps.extend(get_file_items(os.path.join(local.site_path, "apps.txt")))
	if with_frappe:
		apps.insert(0, 'frappe')
	return apps

def get_installed_apps():
	if flags.in_install_db:
		return []
	installed = json.loads(db.get_global("installed_apps") or "[]")
	return installed

def get_hooks(hook=None, default=None, app_name=None):
	def load_app_hooks(app_name=None):
		hooks = {}
		for app in [app_name] if app_name else get_installed_apps():
			app = "frappe" if app=="webnotes" else app
			app_hooks = get_module(app + ".hooks")
			for key in dir(app_hooks):
				if not key.startswith("_"):
					append_hook(hooks, key, getattr(app_hooks, key))
		return hooks

	def append_hook(target, key, value):
		if isinstance(value, dict):
			target.setdefault(key, {})
			for inkey in value:
				append_hook(target[key], inkey, value[inkey])
		else:
			append_to_list(target, key, value)

	def append_to_list(target, key, value):
		target.setdefault(key, [])
		if not isinstance(value, list):
			value = [value]
		target[key].extend(value)

	if app_name:
		hooks = _dict(load_app_hooks(app_name))
	else:
		hooks = _dict(cache().get_value("app_hooks", load_app_hooks))

	if hook:
		return hooks.get(hook) or (default if default is not None else [])
	else:
		return hooks

def setup_module_map():
	_cache = cache()

	if conf.db_name:
		local.app_modules = _cache.get_value("app_modules")
		local.module_app = _cache.get_value("module_app")

	if not local.app_modules:
		local.module_app, local.app_modules = {}, {}
		for app in get_all_apps(True):
			if app=="webnotes": app="frappe"
			local.app_modules.setdefault(app, [])
			for module in get_module_list(app):
				local.module_app[module] = app
				local.app_modules[app].append(module)

		if conf.db_name:
			_cache.set_value("app_modules", local.app_modules)
			_cache.set_value("module_app", local.module_app)

def get_file_items(path, raise_not_found=False):
	content = read_file(path, raise_not_found=raise_not_found)
	if content:
		return [p.strip() for p in content.splitlines() if p.strip() and not p.startswith("#")]
	else:
		return []

def get_file_json(path):
	with open(path, 'r') as f:
		return json.load(f)

def read_file(path, raise_not_found=False):
	from frappe.utils import cstr
	if os.path.exists(path):
		with open(path, "r") as f:
			return cstr(f.read())
	elif raise_not_found:
		raise IOError("{} Not Found".format(path))
	else:
		return None

def get_attr(method_string):
	modulename = '.'.join(method_string.split('.')[:-1])
	methodname = method_string.split('.')[-1]
	return getattr(get_module(modulename), methodname)

def call(fn, *args, **kwargs):
	if hasattr(fn, 'fnargs'):
		fnargs = fn.fnargs
	else:
		fnargs, varargs, varkw, defaults = inspect.getargspec(fn)

	newargs = {}
	for a in fnargs:
		if a in kwargs:
			newargs[a] = kwargs.get(a)
	return fn(*args, **newargs)

def make_property_setter(args):
	args = _dict(args)
	get_doc({
		'doctype': "Property Setter",
		'doctype_or_field': args.doctype_or_field or "DocField",
		'doc_type': args.doctype,
		'field_name': args.fieldname,
		'property': args.property,
		'value': args.value,
		'property_type': args.property_type or "Data",
		'__islocal': 1
	}).save()

def import_doc(path, ignore_links=False, ignore_insert=False, insert=False):
	from frappe.core.page.data_import_tool import data_import_tool
	data_import_tool.import_doc(path, ignore_links=ignore_links, ignore_insert=ignore_insert, insert=insert)

def copy_doc(doc):
	import copy
	if not isinstance(doc, dict):
		d = doc.as_dict()
	else:
		d = doc

	newdoc = get_doc(copy.deepcopy(d))
	newdoc.name = None
	newdoc.set("__islocal", 1)
	newdoc.owner = None
	newdoc.creation = None
	for d in newdoc.get_all_children():
		d.name = None
		d.parent = None
		d.set("__islocal", 1)
		d.owner = None
		d.creation = None
	return newdoc

def compare(val1, condition, val2):
	import frappe.utils
	return frappe.utils.compare(val1, condition, val2)

def respond_as_web_page(title, html, success=None, http_status_code=None):
	local.message_title = title
	local.message = html
	local.message_success = success
	local.response['type'] = 'page'
	local.response['page_name'] = 'message.html'
	if http_status_code:
		local.response['http_status_code'] = http_status_code

def build_match_conditions(doctype, as_condition=True):
	import frappe.widgets.reportview
	return frappe.widgets.reportview.build_match_conditions(doctype, as_condition)

def get_list(doctype, filters=None, fields=None, docstatus=None,
			group_by=None, order_by=None, limit_start=0, limit_page_length=None,
			as_list=False, debug=False, ignore_permissions=False):
	import frappe.model.db_query
	return frappe.model.db_query.DatabaseQuery(doctype).execute(filters=filters, fields=fields, docstatus=docstatus,
				group_by=group_by, order_by=order_by, limit_start=limit_start, limit_page_length=limit_page_length,
				as_list=as_list, debug=debug, ignore_permissions=ignore_permissions)

run_query = get_list

def get_jenv():
	if not local.jenv:
		from jinja2 import Environment, DebugUndefined
		import frappe.utils

		# frappe will be loaded last, so app templates will get precedence
		jenv = Environment(loader = get_jloader(), undefined=DebugUndefined)
		set_filters(jenv)

		jenv.globals.update({
			"frappe": sys.modules[__name__],
			"frappe.utils": frappe.utils,
			"_": _
		})

		local.jenv = jenv

	return local.jenv

def get_jloader():
	if not local.jloader:
		from jinja2 import ChoiceLoader, PackageLoader

		apps = get_installed_apps()
		apps.remove("frappe")

		local.jloader = ChoiceLoader([PackageLoader(app, ".") \
				for app in apps + ["frappe"]])

	return local.jloader

def set_filters(jenv):
	from frappe.utils import global_date_format
	from frappe.website.utils import get_hex_shade
	from markdown2 import markdown
	from json import dumps

	jenv.filters["global_date_format"] = global_date_format
	jenv.filters["markdown"] = markdown
	jenv.filters["json"] = dumps
	jenv.filters["get_hex_shade"] = get_hex_shade

	# load jenv_filters from hooks.txt
	for app in get_all_apps(True):
		for jenv_filter in (get_hooks(app_name=app).jenv_filter or []):
			filter_name, filter_function = jenv_filter.split(":")
			jenv.filters[filter_name] = get_attr(filter_function)

def get_template(path):
	return get_jenv().get_template(path)

def get_website_route(doctype, name):
	return db.get_value("Website Route", {"ref_doctype": doctype, "docname": name})

def add_version(doc):
	get_doc({
		"doctype": "Version",
		"ref_doctype": doc.doctype,
		"docname": doc.name,
		"doclist_json": json.dumps(doc.as_dict(), indent=1, sort_keys=True)
	}).insert(ignore_permissions=True)

def get_test_records(doctype):
	from frappe.modules import get_doctype_module, get_module_path
	path = os.path.join(get_module_path(get_doctype_module(doctype)), "doctype", scrub(doctype), "test_records.json")
	if os.path.exists(path):
		with open(path, "r") as f:
			return json.loads(f.read())
	else:
		return []
