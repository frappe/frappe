# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
"""
globals attached to frappe module
+ some utility functions that should probably be moved
"""
from __future__ import unicode_literals

from werkzeug.local import Local, release_local
from functools import wraps
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

def _(msg, lang=None):
	"""Returns translated string in current lang, if exists."""
	if not lang:
		lang = local.lang

	if lang == "en":
		return msg

	from frappe.translate import get_full_dict
	return get_full_dict(local.lang).get(msg) or msg

def get_lang_dict(fortype, name=None):
	"""Returns the translated language dict for the given type and name.

	 :param fortype: must be one of `doctype`, `page`, `report`, `include`, `jsfile`, `boot`
	 :param name: name of the document for which assets are to be returned."""
	if local.lang=="en":
		return {}
	from frappe.translate import get_dict
	return get_dict(fortype, name)

def set_user_lang(user, user_language=None):
	"""Guess and set user language for the session. `frappe.local.lang`"""
	from frappe.translate import get_user_lang
	local.lang = get_user_lang(user)

# local-globals
db = local("db")
conf = local("conf")
form = form_dict = local("form_dict")
request = local("request")
response = local("response")
session = local("session")
user = local("user")
flags = local("flags")

error_log = local("error_log")
debug_log = local("debug_log")
message_log = local("message_log")

lang = local("lang")

def init(site, sites_path=None):
	"""Initialize frappe for the current site. Reset thread locals `frappe.local`"""
	if getattr(local, "initialised", None):
		return

	if not sites_path:
		sites_path = '.'

	local.error_log = []
	local.message_log = []
	local.debug_log = []
	local.realtime_log = []
	local.flags = _dict({
		"ran_schedulers": [],
		"redirect_location": "",
		"in_install_db": False,
		"in_install_app": False,
		"in_import": False,
		"in_test": False,
		"mute_messages": False,
		"ignore_links": False,
		"mute_emails": False,
		"has_dataurl": False,
	})
	local.rollback_observers = []
	local.test_objects = {}

	local.site = site
	local.sites_path = sites_path
	local.site_path = os.path.join(sites_path, site)

	local.request_ip = None
	local.response = _dict({"docs":[]})
	local.task_id = None

	local.conf = _dict(get_site_config())
	local.lang = local.conf.lang or "en"
	local.lang_full_dict = None

	local.module_app = None
	local.app_modules = None
	local.system_settings = None

	local.user = None
	local.user_obj = None
	local.session = None
	local.role_permissions = {}
	local.valid_columns = {}
	local.new_doc_templates = {}

	local.jenv = None
	local.jloader =None
	local.cache = {}

	setup_module_map()

	local.initialised = True

def connect(site=None, db_name=None):
	"""Connect to site database instance.

	:param site: If site is given, calls `frappe.init`.
	:param db_name: Optional. Will use from `site_config.json`."""
	from database import Database
	if site:
		init(site)
	local.db = Database(user=db_name or local.conf.db_name)
	local.form_dict = _dict()
	local.session = _dict()
	set_user("Administrator")

def get_site_config(sites_path=None, site_path=None):
	"""Returns `site_config.json` combined with `sites/common_site_config.json`.
	`site_config` is a set of site wide settings like database name, password, email etc."""
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
	"""Closes connection and releases werkzeug local."""
	if db:
		db.close()

	release_local(local)

# memcache
redis_server = None
def cache():
	"""Returns memcache connection."""
	global redis_server
	if not redis_server:
		from frappe.utils.redis_wrapper import RedisWrapper
		redis_server = RedisWrapper.from_url(conf.get("cache_redis_server") or "redis://localhost:11311")
	return redis_server

def get_traceback():
	"""Returns error traceback."""
	import utils
	return utils.get_traceback()

def errprint(msg):
	"""Log error. This is sent back as `exc` in response.

	:param msg: Message."""
	from utils import cstr
	if not request or (not "cmd" in local.form_dict):
		print cstr(msg)

	error_log.append(cstr(msg))

def log(msg):
	"""Add to `debug_log`.

	:param msg: Message."""
	if not request:
		if conf.get("logging") or False:
			print repr(msg)

	from utils import cstr
	debug_log.append(cstr(msg))

def msgprint(msg, small=0, raise_exception=0, as_table=False):
	"""Print a message to the user (via HTTP response).
	Messages are sent in the `__server_messages` property in the
	response JSON and shown in a pop-up / modal.

	:param msg: Message.
	:param small: [optional] Show as a floating message in the footer.
	:param raise_exception: [optional] Raise given exception and show message.
	:param as_table: [optional] If `msg` is a list of lists, render as HTML table.
	"""
	from utils import cstr, encode

	def _raise_exception():
		if raise_exception:
			if flags.rollback_on_exception:
				db.rollback()
			import inspect
			if inspect.isclass(raise_exception) and issubclass(raise_exception, Exception):
				raise raise_exception, encode(msg)
			else:
				raise ValidationError, encode(msg)

	if flags.mute_messages:
		_raise_exception()
		return

	if as_table and type(msg) in (list, tuple):
		msg = '<table border="1px" style="border-collapse: collapse" cellpadding="2px">' + ''.join(['<tr>'+''.join(['<td>%s</td>' % c for c in r])+'</tr>' for r in msg]) + '</table>'

	if flags.print_messages:
		print "Message: " + repr(msg).encode("utf-8")

	message_log.append((small and '__small:' or '')+cstr(msg or ''))
	_raise_exception()

def throw(msg, exc=ValidationError):
	"""Throw execption and show message (`msgprint`).

	:param msg: Message.
	:param exc: Exception class. Default `frappe.ValidationError`"""
	msgprint(msg, raise_exception=exc)

def create_folder(path, with_init=False):
	"""Create a folder in the given path and add an `__init__.py` file (optional).

	:param path: Folder path.
	:param with_init: Create `__init__.py` in the new folder."""
	from frappe.utils import touch_file
	if not os.path.exists(path):
		os.makedirs(path)

		if with_init:
			touch_file(os.path.join(path, "__init__.py"))

def set_user(username):
	"""Set current user.

	:param username: **User** name to set as current user."""
	local.session.user = username
	local.session.sid = username
	local.cache = {}
	local.form_dict = _dict()
	local.jenv = None
	local.session.data = _dict()
	local.role_permissions = {}
	local.new_doc_templates = {}
	local.user_obj = None

def get_user():
	from frappe.utils.user import User
	if not local.user_obj:
		local.user_obj = User(local.session.user)
	return local.user_obj

def get_roles(username=None):
	"""Returns roles of current user."""
	if not local.session:
		return ["Guest"]

	if username:
		import frappe.utils.user
		return frappe.utils.user.get_roles(username)
	else:
		return get_user().get_roles()

def get_request_header(key, default=None):
	"""Return HTTP request header.

	:param key: HTTP header key.
	:param default: Default value."""
	return request.headers.get(key, default)

def sendmail(recipients=(), sender="", subject="No Subject", message="No Message",
		as_markdown=False, bulk=False, reference_doctype=None, reference_name=None,
		unsubscribe_method=None, unsubscribe_params=None, unsubscribe_message=None,
		attachments=None, content=None, doctype=None, name=None, reply_to=None,
		cc=(), show_as_cc=(), message_id=None, as_bulk=False, send_after=None, expose_recipients=False,
		bulk_priority=1):
	"""Send email using user's default **Email Account** or global default **Email Account**.


	:param recipients: List of recipients.
	:param sender: Email sender. Default is current user.
	:param subject: Email Subject.
	:param message: (or `content`) Email Content.
	:param as_markdown: Convert content markdown to HTML.
	:param bulk: Send via scheduled email sender **Bulk Email**. Don't send immediately.
	:param bulk_priority: Priority for bulk email, default 1.
	:param reference_doctype: (or `doctype`) Append as communication to this DocType.
	:param reference_name: (or `name`) Append as communication to this document name.
	:param unsubscribe_method: Unsubscribe url with options email, doctype, name. e.g. `/api/method/unsubscribe`
	:param unsubscribe_params: Unsubscribe paramaters to be loaded on the unsubscribe_method [optional] (dict).
	:param attachments: List of attachments.
	:param reply_to: Reply-To email id.
	:param message_id: Used for threading. If a reply is received to this email, Message-Id is sent back as In-Reply-To in received email.
	:param send_after: Send after the given datetime.
	:param expose_recipients: Display all recipients in the footer message - "This email was sent to"
	"""

	if bulk or as_bulk:
		import frappe.email.bulk
		frappe.email.bulk.send(recipients=recipients, sender=sender,
			subject=subject, message=content or message,
			reference_doctype = doctype or reference_doctype, reference_name = name or reference_name,
			unsubscribe_method=unsubscribe_method, unsubscribe_params=unsubscribe_params, unsubscribe_message=unsubscribe_message,
			attachments=attachments, reply_to=reply_to, cc=cc, show_as_cc=show_as_cc, message_id=message_id, send_after=send_after,
			expose_recipients=expose_recipients, bulk_priority=bulk_priority)
	else:
		import frappe.email
		if as_markdown:
			frappe.email.sendmail_md(recipients, sender=sender,
				subject=subject, msg=content or message, attachments=attachments, reply_to=reply_to,
				cc=cc, message_id=message_id)
		else:
			frappe.email.sendmail(recipients, sender=sender,
				subject=subject, msg=content or message, attachments=attachments, reply_to=reply_to,
				cc=cc, message_id=message_id)

logger = None
whitelisted = []
guest_methods = []
xss_safe_methods = []
def whitelist(allow_guest=False, xss_safe=False):
	"""
	Decorator for whitelisting a function and making it accessible via HTTP.
	Standard request will be `/api/method/[path.to.method]`

	:param allow_guest: Allow non logged-in user to access this method.

	Use as:

		@frappe.whitelist()
		def myfunc(param1, param2):
			pass
	"""
	def innerfn(fn):
		global whitelisted, guest_methods, xss_safe_methods
		whitelisted.append(fn)

		if allow_guest:
			guest_methods.append(fn)

			if xss_safe:
				xss_safe_methods.append(fn)

		return fn

	return innerfn

def only_for(roles):
	"""Raise `frappe.PermissionError` if the user does not have any of the given **Roles**.

	:param roles: List of roles to check."""
	if not isinstance(roles, (tuple, list)):
		roles = (roles,)
	roles = set(roles)
	myroles = set(get_roles())
	if not roles.intersection(myroles):
		raise PermissionError

def clear_cache(user=None, doctype=None):
	"""Clear **User**, **DocType** or global cache.

	:param user: If user is given, only user cache is cleared.
	:param doctype: If doctype is given, only DocType cache is cleared."""
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
		frappe.local.cache = {}

		for fn in frappe.get_hooks("clear_cache"):
			get_attr(fn)()

	frappe.local.role_permissions = {}

def has_permission(doctype, ptype="read", doc=None, user=None, verbose=False):
	"""Raises `frappe.PermissionError` if not permitted.

	:param doctype: DocType for which permission is to be check.
	:param ptype: Permission type (`read`, `write`, `create`, `submit`, `cancel`, `amend`). Default: `read`.
	:param doc: [optional] Checks User permissions for given doc.
	:param user: [optional] Check for given user. Default: current user."""
	import frappe.permissions
	return frappe.permissions.has_permission(doctype, ptype, doc=doc, verbose=verbose, user=user)

def has_website_permission(doctype, ptype="read", doc=None, user=None, verbose=False):
	"""Raises `frappe.PermissionError` if not permitted.

	:param doctype: DocType for which permission is to be check.
	:param ptype: Permission type (`read`, `write`, `create`, `submit`, `cancel`, `amend`). Default: `read`.
	:param doc: Checks User permissions for given doc.
	:param user: [optional] Check for given user. Default: current user."""

	if not user:
		user = session.user

	hooks = (get_hooks("has_website_permission") or {}).get(doctype, [])
	if hooks:
		if isinstance(doc, basestring):
			doc = get_doc(doctype, doc)

		for method in hooks:
			result = call(get_attr(method), doc=doc, ptype=ptype, user=user, verbose=verbose)
			# if even a single permission check is Falsy
			if not result:
				return False

		# else it is Truthy
		return True

	else:
		return False

def is_table(doctype):
	"""Returns True if `istable` property (indicating child Table) is set for given DocType."""
	def get_tables():
		return db.sql_list("select name from tabDocType where istable=1")

	tables = cache().get_value("is_table", get_tables)
	return doctype in tables

def get_precision(doctype, fieldname, currency=None, doc=None):
	"""Get precision for a given field"""
	from frappe.model.meta import get_field_precision
	return get_field_precision(get_meta(doctype).get_field(fieldname), doc, currency)

def generate_hash(txt=None, length=None):
	"""Generates random hash for given text + current timestamp + random string."""
	import hashlib, time
	from .utils import random_string
	digest = hashlib.sha224((txt or "") + repr(time.time()) + repr(random_string(8))).hexdigest()
	if length:
		digest = digest[:length]
	return digest

def reset_metadata_version():
	"""Reset `metadata_version` (Client (Javascript) build ID) hash."""
	v = generate_hash()
	cache().set_value("metadata_version", v)
	return v

def new_doc(doctype, parent_doc=None, parentfield=None, as_dict=False):
	"""Returns a new document of the given DocType with defaults set.

	:param doctype: DocType of the new document.
	:param parent_doc: [optional] add to parent document.
	:param parentfield: [optional] add against this `parentfield`."""
	from frappe.model.create_new import get_new_doc
	return get_new_doc(doctype, parent_doc, parentfield, as_dict=as_dict)

def set_value(doctype, docname, fieldname, value):
	"""Set document value. Calls `frappe.client.set_value`"""
	import frappe.client
	return frappe.client.set_value(doctype, docname, fieldname, value)

def get_doc(arg1, arg2=None):
	"""Return a `frappe.model.document.Document` object of the given type and name.

	:param arg1: DocType name as string **or** document JSON.
	:param arg2: [optional] Document name as string.

	Examples:

		# insert a new document
		todo = frappe.get_doc({"doctype":"ToDo", "description": "test"})
		tood.insert()

		# open an existing document
		todo = frappe.get_doc("ToDo", "TD0001")

	"""
	import frappe.model.document
	return frappe.model.document.get_doc(arg1, arg2)

def get_last_doc(doctype):
	"""Get last created document of this type."""
	d = get_all(doctype, ["name"], order_by="creation desc", limit_page_length=1)
	if d:
		return get_doc(doctype, d[0].name)
	else:
		raise DoesNotExistError

def get_single(doctype):
	"""Return a `frappe.model.document.Document` object of the given Single doctype."""
	return get_doc(doctype, doctype)

def get_meta(doctype, cached=True):
	"""Get `frappe.model.meta.Meta` instance of given doctype name."""
	import frappe.model.meta
	return frappe.model.meta.get_meta(doctype, cached=cached)

def get_meta_module(doctype):
	import frappe.modules
	return frappe.modules.load_doctype_module(doctype)

def delete_doc(doctype=None, name=None, force=0, ignore_doctypes=None, for_reload=False,
	ignore_permissions=False, flags=None):
	"""Delete a document. Calls `frappe.model.delete_doc.delete_doc`.

	:param doctype: DocType of document to be delete.
	:param name: Name of document to be delete.
	:param force: Allow even if document is linked. Warning: This may lead to data integrity errors.
	:param ignore_doctypes: Ignore if child table is one of these.
	:param for_reload: Call `before_reload` trigger before deleting.
	:param ignore_permissions: Ignore user permissions."""
	import frappe.model.delete_doc
	frappe.model.delete_doc.delete_doc(doctype, name, force, ignore_doctypes, for_reload,
		ignore_permissions, flags)

def delete_doc_if_exists(doctype, name):
	"""Delete document if exists."""
	if db.exists(doctype, name):
		delete_doc(doctype, name)

def reload_doctype(doctype, force=False):
	"""Reload DocType from model (`[module]/[doctype]/[name]/[name].json`) files."""
	reload_doc(scrub(db.get_value("DocType", doctype, "module")), "doctype", scrub(doctype), force=force)

def reload_doc(module, dt=None, dn=None, force=False):
	"""Reload Document from model (`[module]/[doctype]/[name]/[name].json`) files.

	:param module: Module name.
	:param dt: DocType name.
	:param dn: Document name.
	:param force: Reload even if `modified` timestamp matches.
	"""

	import frappe.modules
	return frappe.modules.reload_doc(module, dt, dn, force=force)

def rename_doc(doctype, old, new, debug=0, force=False, merge=False, ignore_permissions=False):
	"""Rename a document. Calls `frappe.model.rename_doc.rename_doc`"""
	from frappe.model.rename_doc import rename_doc
	return rename_doc(doctype, old, new, force=force, merge=merge, ignore_permissions=ignore_permissions)

def get_module(modulename):
	"""Returns a module object for given Python module name using `importlib.import_module`."""
	return importlib.import_module(modulename)

def scrub(txt):
	"""Returns sluggified string. e.g. `Sales Order` becomes `sales_order`."""
	return txt.replace(' ','_').replace('-', '_').lower()

def unscrub(txt):
	"""Returns titlified string. e.g. `sales_order` becomes `Sales Order`."""
	return txt.replace('_',' ').replace('-', ' ').title()

def get_module_path(module, *joins):
	"""Get the path of the given module name.

	:param module: Module name.
	:param *joins: Join additional path elements using `os.path.join`."""
	module = scrub(module)
	return get_pymodule_path(local.module_app[module] + "." + module, *joins)

def get_app_path(app_name, *joins):
	"""Return path of given app.

	:param app: App name.
	:param *joins: Join additional path elements using `os.path.join`."""
	return get_pymodule_path(app_name, *joins)

def get_site_path(*joins):
	"""Return path of current site.

	:param *joins: Join additional path elements using `os.path.join`."""
	return os.path.join(local.site_path, *joins)

def get_pymodule_path(modulename, *joins):
	"""Return path of given Python module name.

	:param modulename: Python module name.
	:param *joins: Join additional path elements using `os.path.join`."""
	if not "public" in joins:
		joins = [scrub(part) for part in joins]
	return os.path.join(os.path.dirname(get_module(scrub(modulename)).__file__), *joins)

def get_module_list(app_name):
	"""Get list of modules for given all via `app/modules.txt`."""
	return get_file_items(os.path.join(os.path.dirname(get_module(app_name).__file__), "modules.txt"))

def get_all_apps(with_frappe=False, with_internal_apps=True, sites_path=None):
	"""Get list of all apps via `sites/apps.txt`."""
	if not sites_path:
		sites_path = local.sites_path

	apps = get_file_items(os.path.join(sites_path, "apps.txt"), raise_not_found=True)
	if with_internal_apps:
		apps.extend(get_file_items(os.path.join(local.site_path, "apps.txt")))
	if with_frappe:
		if "frappe" in apps:
			apps.remove("frappe")
		apps.insert(0, 'frappe')
	return apps

def get_installed_apps(sort=False):
	"""Get list of installed apps in current site."""
	if getattr(flags, "in_install_db", True):
		return []

	if not db:
		connect()

	installed = json.loads(db.get_global("installed_apps") or "[]")

	if sort:
		installed = [app for app in get_all_apps(True) if app in installed]

	return installed

def get_hooks(hook=None, default=None, app_name=None):
	"""Get hooks via `app/hooks.py`

	:param hook: Name of the hook. Will gather all hooks for this name and return as a list.
	:param default: Default if no hook found.
	:param app_name: Filter by app."""
	def load_app_hooks(app_name=None):
		hooks = {}
		for app in [app_name] if app_name else get_installed_apps(sort=True):
			app = "frappe" if app=="webnotes" else app
			try:
				app_hooks = get_module(app + ".hooks")
			except ImportError:
				if local.flags.in_install_app:
					# if app is not installed while restoring
					# ignore it
					pass
				raise
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
	"""Rebuild map of all modules (internal)."""
	_cache = cache()

	if conf.db_name:
		local.app_modules = _cache.get_value("app_modules")
		local.module_app = _cache.get_value("module_app")

	if not (local.app_modules and local.module_app):
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
	"""Returns items from text file as a list. Ignores empty lines."""
	import frappe.utils

	content = read_file(path, raise_not_found=raise_not_found)
	if content:
		content = frappe.utils.strip(content)

		return [p.strip() for p in content.splitlines() if (not ignore_empty_lines) or (p.strip() and not p.startswith("#"))]
	else:
		return []

def get_file_json(path):
	"""Read a file and return parsed JSON object."""
	with open(path, 'r') as f:
		return json.load(f)

def read_file(path, raise_not_found=False):
	"""Open a file and return its content as Unicode."""
	from frappe.utils import cstr
	if isinstance(path, unicode):
		path = path.encode("utf-8")

	if os.path.exists(path):
		with open(path, "r") as f:
			return cstr(f.read())
	elif raise_not_found:
		raise IOError("{} Not Found".format(path))
	else:
		return None

def get_attr(method_string):
	"""Get python method object from its name."""
	app_name = method_string.split(".")[0]
	if not local.flags.in_install and app_name not in get_installed_apps():
		throw(_("App {0} is not installed").format(app_name), AppNotInstalledError)

	modulename = '.'.join(method_string.split('.')[:-1])
	methodname = method_string.split('.')[-1]
	return getattr(get_module(modulename), methodname)

def call(fn, *args, **kwargs):
	"""Call a function and match arguments."""
	if hasattr(fn, 'fnargs'):
		fnargs = fn.fnargs
	else:
		fnargs, varargs, varkw, defaults = inspect.getargspec(fn)

	newargs = {}
	for a in kwargs:
		if (a in fnargs) or varkw:
			newargs[a] = kwargs.get(a)

	if "flags" in newargs:
		del newargs["flags"]

	return fn(*args, **newargs)

def make_property_setter(args, ignore_validate=False, validate_fields_for_doctype=True):
	"""Create a new **Property Setter** (for overriding DocType and DocField properties)."""
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
	ps.flags.ignore_validate = ignore_validate
	ps.flags.validate_fields_for_doctype = validate_fields_for_doctype
	ps.insert()

def import_doc(path, ignore_links=False, ignore_insert=False, insert=False):
	"""Import a file using Data Import Tool."""
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
	"""Compare two values using `frappe.utils.compare`

	`condition` could be:
	- "^"
	- "in"
	- "not in"
	- "="
	- "!="
	- ">"
	- "<"
	- ">="
	- "<="
	- "not None"
	- "None"
	"""
	import frappe.utils
	return frappe.utils.compare(val1, condition, val2)

def respond_as_web_page(title, html, success=None, http_status_code=None):
	"""Send response as a web page with a message rather than JSON. Used to show permission errors etc.

	:param title: Page title and heading.
	:param message: Message to be shown.
	:param success: Alert message.
	:param http_status_code: HTTP status code."""
	local.message_title = title
	local.message = html
	local.message_success = success
	local.response['type'] = 'page'
	local.response['page_name'] = 'message'
	if http_status_code:
		local.response['http_status_code'] = http_status_code

def build_match_conditions(doctype, as_condition=True):
	"""Return match (User permissions) for given doctype as list or SQL."""
	import frappe.desk.reportview
	return frappe.desk.reportview.build_match_conditions(doctype, as_condition)

def get_list(doctype, *args, **kwargs):
	"""List database query via `frappe.model.db_query`. Will also check for permissions.

	:param doctype: DocType on which query is to be made.
	:param fields: List of fields or `*`.
	:param filters: List of filters (see example).
	:param order_by: Order By e.g. `modified desc`.
	:param limit_page_start: Start results at record #. Default 0.
	:param limit_poge_length: No of records in the page. Default 20.

	Example usage:

		# simple dict filter
		frappe.get_list("ToDo", fields=["name", "description"], filters = {"owner":"test@example.com"})

		# filter as a list of lists
		frappe.get_list("ToDo", fields="*", filters = [["modified", ">", "2014-01-01"]])

		# filter as a list of dicts
		frappe.get_list("ToDo", fields="*", filters = {"description": ("like", "test%")})
	"""
	import frappe.model.db_query
	return frappe.model.db_query.DatabaseQuery(doctype).execute(None, *args, **kwargs)

def get_all(doctype, *args, **kwargs):
	"""List database query via `frappe.model.db_query`. Will **not** check for conditions.
	Parameters are same as `frappe.get_list`

	:param doctype: DocType on which query is to be made.
	:param fields: List of fields or `*`. Default is: `["name"]`.
	:param filters: List of filters (see example).
	:param order_by: Order By e.g. `modified desc`.
	:param limit_page_start: Start results at record #. Default 0.
	:param limit_poge_length: No of records in the page. Default 20.

	Example usage:

		# simple dict filter
		frappe.get_all("ToDo", fields=["name", "description"], filters = {"owner":"test@example.com"})

		# filter as a list of lists
		frappe.get_all("ToDo", fields=["*"], filters = [["modified", ">", "2014-01-01"]])

		# filter as a list of dicts
		frappe.get_all("ToDo", fields=["*"], filters = {"description": ("like", "test%")})
	"""
	kwargs["ignore_permissions"] = True
	if not "limit_page_length" in kwargs:
		kwargs["limit_page_length"] = 0
	return get_list(doctype, *args, **kwargs)

def get_value(*args, **kwargs):
	"""Returns a document property or list of properties.

	Alias for `frappe.db.get_value`

	:param doctype: DocType name.
	:param filters: Filters like `{"x":"y"}` or name of the document. `None` if Single DocType.
	:param fieldname: Column name.
	:param ignore: Don't raise exception if table, column is missing.
	:param as_dict: Return values as dict.
	:param debug: Print query in error log.
	"""
	return db.get_value(*args, **kwargs)

def add_version(doc):
	"""Insert a new **Version** of the given document.
	A **Version** is a JSON dump of the current document state."""
	get_doc({
		"doctype": "Version",
		"ref_doctype": doc.doctype,
		"docname": doc.name,
		"doclist_json": as_json(doc.as_dict())
	}).insert(ignore_permissions=True)

def as_json(obj, indent=1):
	from frappe.utils.response import json_handler
	return json.dumps(obj, indent=indent, sort_keys=True, default=json_handler)

def are_emails_muted():
	return flags.mute_emails or conf.get("mute_emails") or False

def get_test_records(doctype):
	"""Returns list of objects from `test_records.json` in the given doctype's folder."""
	from frappe.modules import get_doctype_module, get_module_path
	path = os.path.join(get_module_path(get_doctype_module(doctype)), "doctype", scrub(doctype), "test_records.json")
	if os.path.exists(path):
		with open(path, "r") as f:
			return json.loads(f.read())
	else:
		return []

def format_value(value, df, doc=None, currency=None):
	"""Format value with given field properties.

	:param value: Value to be formatted.
	:param df: DocField object with properties `fieldtype`, `options` etc."""
	import frappe.utils.formatters
	return frappe.utils.formatters.format_value(value, df, doc, currency=currency)

def get_print(doctype, name, print_format=None, style=None, html=None, as_pdf=False):
	"""Get Print Format for given document.

	:param doctype: DocType of document.
	:param name: Name of document.
	:param print_format: Print Format name. Default 'Standard',
	:param style: Print Format style.
	:param as_pdf: Return as PDF. Default False."""
	from frappe.website.render import build_page
	from frappe.utils.pdf import get_pdf

	local.form_dict.doctype = doctype
	local.form_dict.name = name
	local.form_dict.format = print_format
	local.form_dict.style = style

	if not html:
		html = build_page("print")

	if as_pdf:
		return get_pdf(html)
	else:
		return html

def attach_print(doctype, name, file_name=None, print_format=None, style=None, html=None):
	from frappe.utils import scrub_urls

	if not file_name: file_name = name
	file_name = file_name.replace(' ','').replace('/','-')

	print_settings = db.get_singles_dict("Print Settings")

	local.flags.ignore_print_permissions = True

	if int(print_settings.send_print_as_pdf or 0):
		out = {
			"fname": file_name + ".pdf",
			"fcontent": get_print(doctype, name, print_format=print_format, style=style, html=html, as_pdf=True)
		}
	else:
		out = {
			"fname": file_name + ".html",
			"fcontent": scrub_urls(get_print(doctype, name, print_format=print_format, style=style, html=html)).encode("utf-8")
		}

	local.flags.ignore_print_permissions = False

	return out

logging_setup_complete = False
def get_logger(module=None):
	from frappe.setup_logging import setup_logging
	global logging_setup_complete

	if not logging_setup_complete:
		setup_logging()
		logging_setup_complete = True

	return logging.getLogger(module or "frappe")

def publish_realtime(*args, **kwargs):
	"""Publish real-time updates

	:param event: Event name, like `task_progress` etc.
	:param message: JSON message object. For async must contain `task_id`
	:param room: Room in which to publish update (default entire site)
	:param user: Transmit to user
	:param doctype: Transmit to doctype, docname
	:param docname: Transmit to doctype, docname"""
	import frappe.async

	return frappe.async.publish_realtime(*args, **kwargs)

def local_cache(namespace, key, generator, regenerate_if_none=False):
	"""A key value store for caching within a request

	:param namespace: frappe.local.cache[namespace]
	:param key: frappe.local.cache[namespace][key] used to retrieve value
	:param generator: method to generate a value if not found in store

	"""
	if namespace not in local.cache:
		local.cache[namespace] = {}

	if key not in local.cache[namespace]:
		local.cache[namespace][key] = generator()

	elif local.cache[namespace][key]==None and regenerate_if_none:
		# if key exists but the previous result was None
		local.cache[namespace][key] = generator()

	return local.cache[namespace][key]

def get_doctype_app(doctype):
	def _get_doctype_app():
		doctype_module = local.db.get_value("DocType", doctype, "module")
		return local.module_app[scrub(doctype_module)]

	return local_cache("doctype_app", doctype, generator=_get_doctype_app)
