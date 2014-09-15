# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
"""
globals attached to frappe module
+ some utility functions that should probably be moved
"""
from __future__ import unicode_literals

from werkzeug.local import Local, release_local
import os, importlib, inspect, logging, json

# public
from frappe.__version__ import __version__
from .exceptions import *
from .utils.jinja import get_jenv, get_template, render_template

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
	local.message_log = []
	local.debug_log = []
	local.flags = _dict({})
	local.rollback_observers = []
	local.test_objects = {}

	local.site = site
	local.sites_path = sites_path
	local.site_path = os.path.join(sites_path, site)

	local.request_method = request.method if request else None
	local.request_ip = None
	local.response = _dict({"docs":[]})

	local.conf = _dict(get_site_config())
	local.lang = local.conf.lang or "en"

	local.module_app = None
	local.app_modules = None

	local.user = None
	local.role_permissions = {}

	local.jenv = None
	local.jloader =None
	local.cache = {}

	setup_module_map()

	local.initialised = True

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
	if not request or (not "cmd" in local.form_dict):
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

def create_folder(path, with_init=False):
	from frappe.utils import touch_file
	if not os.path.exists(path):
		os.makedirs(path)

		if with_init:
			touch_file(os.path.join(path, "__init__.py"))

def set_user(username):
	from frappe.utils.user import User
	local.session.user = username
	local.session.sid = username
	local.cache = {}
	local.form_dict = _dict()
	local.jenv = None
	local.session.data = {}
	local.user = User(username)
	local.role_permissions = {}

def get_request_header(key, default=None):
	return request.headers.get(key, default)

def sendmail(recipients=(), sender="", subject="No Subject", message="No Message",
		as_markdown=False, bulk=False, ref_doctype=None, ref_docname=None,
		add_unsubscribe_link=False, attachments=None):

	if bulk:
		import frappe.utils.email_lib.bulk
		frappe.utils.email_lib.bulk.send(recipients=recipients, sender=sender,
			subject=subject, message=message, ref_doctype = ref_doctype,
			ref_docname = ref_docname, add_unsubscribe_link=add_unsubscribe_link, attachments=attachments)

	else:
		import frappe.utils.email_lib
		if as_markdown:
			frappe.utils.email_lib.sendmail_md(recipients, sender=sender,
				subject=subject, msg=message, attachments=attachments)
		else:
			frappe.utils.email_lib.sendmail(recipients, sender=sender,
				subject=subject, msg=message, attachments=attachments)

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

		for fn in frappe.get_hooks("clear_cache"):
			get_attr(fn)()

	frappe.local.role_permissions = {}

def get_roles(username=None):
	if not local.session:
		return ["Guest"]

	return get_user(username).get_roles()

def get_user(username):
	from frappe.utils.user import User
	if not username or username == local.session.user:
		return local.user
	else:
		return User(username)

def has_permission(doctype, ptype="read", doc=None, user=None):
	import frappe.permissions
	return frappe.permissions.has_permission(doctype, ptype, doc, user=user)

def is_table(doctype):
	tables = cache().get_value("is_table")
	if tables==None:
		tables = db.sql_list("select name from tabDocType where ifnull(istable,0)=1")
		cache().set_value("is_table", tables)
	return doctype in tables

def clear_perms(doctype):
	db.sql("""delete from tabDocPerm where parent=%s""", doctype)

def reset_perms(doctype):
	from frappe.core.doctype.notification_count.notification_count import delete_notification_count_for
	delete_notification_count_for(doctype)

	clear_perms(doctype)
	reload_doc(db.get_value("DocType", doctype, "module"),
		"DocType", doctype, force=True)

def generate_hash(txt=None):
	"""Generates random hash for session id"""
	import hashlib, time
	from .utils import random_string
	return hashlib.sha224((txt or "") + repr(time.time()) + repr(random_string(8))).hexdigest()

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
	return txt.replace(' ','_').replace('-', '_').lower()

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
	if getattr(flags, "in_install_db", True):
		return []
	installed = json.loads(db.get_global("installed_apps") or "[]")
	return installed

@whitelist()
def get_versions():
	versions = {}
	for app in get_installed_apps():
		versions[app] = {
			"title": get_hooks("app_title", app_name=app),
			"description": get_hooks("app_description", app_name=app)
		}
		try:
			versions[app]["version"] = get_attr(app + ".__version__")
		except AttributeError:
			versions[app]["version"] = '0.0.1'

	return versions

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
				module = scrub(module)
				local.module_app[module] = app
				local.app_modules[app].append(module)

		if conf.db_name:
			_cache.set_value("app_modules", local.app_modules)
			_cache.set_value("module_app", local.module_app)

def get_file_items(path, raise_not_found=False, ignore_empty_lines=True):
	content = read_file(path, raise_not_found=raise_not_found)
	if content:
		# \ufeff is no-width-break, \u200b is no-width-space
		content = content.replace("\ufeff", "").replace("\u200b", "").strip()

		return [p.strip() for p in content.splitlines() if (not ignore_empty_lines) or (p.strip() and not p.startswith("#"))]
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

def make_property_setter(args, ignore_validate=False):
	args = _dict(args)
	ps = get_doc({
		'doctype': "Property Setter",
		'doctype_or_field': args.doctype_or_field or "DocField",
		'doc_type': args.doctype,
		'field_name': args.fieldname,
		'property': args.property,
		'value': args.value,
		'property_type': args.property_type or "Data",
		'__islocal': 1
	})
	ps.ignore_validate = ignore_validate
	ps.insert()

def import_doc(path, ignore_links=False, ignore_insert=False, insert=False):
	from frappe.core.page.data_import_tool import data_import_tool
	data_import_tool.import_doc(path, ignore_links=ignore_links, ignore_insert=ignore_insert, insert=insert)

def copy_doc(doc, ignore_no_copy=True):
	""" No_copy fields also get copied."""
	import copy

	def remove_no_copy_fields(d):
		for df in d.meta.get("fields", {"no_copy": 1}):
			if hasattr(d, df.fieldname):
				d.set(df.fieldname, None)

	if not isinstance(doc, dict):
		d = doc.as_dict()
	else:
		d = doc

	newdoc = get_doc(copy.deepcopy(d))
	newdoc.name = None
	newdoc.set("__islocal", 1)
	newdoc.owner = None
	newdoc.creation = None
	newdoc.amended_from = None
	newdoc.amendment_date = None
	if not ignore_no_copy:
		remove_no_copy_fields(newdoc)

	for d in newdoc.get_all_children():
		d.name = None
		d.parent = None
		d.set("__islocal", 1)
		d.owner = None
		d.creation = None
		if not ignore_no_copy:
			remove_no_copy_fields(d)

	return newdoc

def compare(val1, condition, val2):
	import frappe.utils
	return frappe.utils.compare(val1, condition, val2)

def respond_as_web_page(title, html, success=None, http_status_code=None):
	local.message_title = title
	local.message = html
	local.message_success = success
	local.response['type'] = 'page'
	local.response['page_name'] = 'message'
	if http_status_code:
		local.response['http_status_code'] = http_status_code

def build_match_conditions(doctype, as_condition=True):
	import frappe.widgets.reportview
	return frappe.widgets.reportview.build_match_conditions(doctype, as_condition)

def get_list(doctype, filters=None, fields=None, or_filters=None, docstatus=None,
			group_by=None, order_by=None, limit_start=0, limit_page_length=None,
			as_list=False, debug=False, ignore_permissions=False, user=None):
	import frappe.model.db_query
	return frappe.model.db_query.DatabaseQuery(doctype).execute(filters=filters,
				fields=fields, docstatus=docstatus, or_filters=or_filters,
				group_by=group_by, order_by=order_by, limit_start=limit_start,
				limit_page_length=limit_page_length, as_list=as_list, debug=debug,
				ignore_permissions=ignore_permissions, user=user)

run_query = get_list

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

def format_value(value, df, doc=None, currency=None):
	import frappe.utils.formatters
	return frappe.utils.formatters.format_value(value, df, doc, currency=currency)

def get_print_format(doctype, name, print_format=None, style=None, as_pdf=False):
	from frappe.website.render import build_page
	local.form_dict.doctype = doctype
	local.form_dict.name = name
	local.form_dict.format = print_format
	local.form_dict.style = style

	html = build_page("print")

	if as_pdf:
		print_settings = db.get_singles_dict("Print Settings")
		if int(print_settings.send_print_as_pdf or 0):
			from utils.pdf import get_pdf
			return get_pdf(html, {"page-size": print_settings.pdf_page_size})
		else:
			return html
	else:
		return html

logging_setup_complete = False
def get_logger(module=None):
	from frappe.setup_logging import setup_logging
	global logging_setup_complete

	if not logging_setup_complete:
		setup_logging()
		logging_setup_complete = True

	return logging.getLogger(module or "frappe")
