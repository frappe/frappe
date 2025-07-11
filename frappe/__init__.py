# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Frappe - Low Code Open Source Framework in Python and JS

Frappe, pronounced fra-pay, is a full stack, batteries-included, web
framework written in Python and Javascript with MariaDB as the database.
It is the framework which powers ERPNext. It is pretty generic and can
be used to build database driven apps.

Read the documentation: https://frappeframework.com/docs
"""

import functools
import importlib
import inspect
import json
import os
import sys
import threading
import warnings
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import (
	TYPE_CHECKING,
	Any,
	Optional,
	TypeAlias,
	Union,
)

import orjson
from werkzeug.datastructures import Headers

import frappe
from frappe.query_builder.utils import (
	get_query,
	get_query_builder,
)
from frappe.utils.caching import deprecated_local_cache as local_cache
from frappe.utils.caching import request_cache, site_cache
from frappe.utils.data import as_unicode, bold, cint, cstr, safe_decode, safe_encode, sbool
from frappe.utils.local import Local, LocalProxy, release_local
from frappe.utils.translations import _, _lt, set_user_lang

# Local application imports
from .exceptions import *
from .types import _dict
from .utils.jinja import (
	get_email_from_template,
	get_jenv,
	get_jloader,
	get_template,
	render_template,
)

__version__ = "16.0.0-dev"
__title__ = "Frappe Framework"

if TYPE_CHECKING:  # pragma: no cover
	from logging import Logger

	from werkzeug.wrappers import Request

	from frappe.database.mariadb.database import MariaDBDatabase as PyMariaDBDatabase
	from frappe.database.mariadb.mysqlclient import MariaDBDatabase
	from frappe.database.postgres.database import PostgresDatabase
	from frappe.database.sqlite.database import SQLiteDatabase
	from frappe.model.document import Document
	from frappe.query_builder.builder import MariaDB, Postgres, SQLite
	from frappe.utils.redis_wrapper import ClientCache, RedisWrapper

controllers: dict[str, type] = {}
lazy_controllers: dict[str, type] = {}
local = Local()
cache: Optional["RedisWrapper"] = None
client_cache: Optional["ClientCache"] = None
STANDARD_USERS = ("Guest", "Administrator")

# this global may be subsequently changed by frappe.tests.utils.toggle_test_mode()
in_test = False

_dev_server = int(sbool(os.environ.get("DEV_SERVER", False)))

if _dev_server:
	warnings.simplefilter("always", DeprecationWarning)
	warnings.simplefilter("always", PendingDeprecationWarning)


# local-globals
ConfType: TypeAlias = _dict[str, Any]  # type: ignore[no-any-explicit]
# TODO: make session a dataclass instead of undtyped _dict
SessionType: TypeAlias = _dict[str, Any]  # type: ignore[no-any-explicit]
# TODO: implement dataclass
LogMessageType: TypeAlias = _dict[str, Any]  # type: ignore[no-any-explicit]
# TODO: implement dataclass
# holds job metadata if the code is run in a background job context
JobMetaType: TypeAlias = _dict[str, Any]  # type: ignore[no-any-explicit]
ResponseDict: TypeAlias = _dict[str, Any]  # type: ignore[no-any-explicit]
FlagsDict: TypeAlias = _dict[str, Any]  # type: ignore[no-any-explicit]
FormDict: TypeAlias = _dict[str, str]

db: LocalProxy[Union["PyMariaDBDatabase", "MariaDBDatabase", "PostgresDatabase", "SQLiteDatabase"]] = local(
	"db"
)
qb: LocalProxy[Union["MariaDB", "Postgres", "SQLite"]] = local("qb")
conf: LocalProxy[ConfType] = local("conf")
form_dict: LocalProxy[FormDict] = local("form_dict")
form = form_dict
request: LocalProxy["Request"] = local("request")
job: LocalProxy[JobMetaType] = local("job")
response: LocalProxy[ResponseDict] = local("response")
session: LocalProxy[SessionType] = local("session")
user: LocalProxy[str] = local("user")
flags: LocalProxy[FlagsDict] = local("flags")

error_log: LocalProxy[list[dict[str, str]]] = local("error_log")
debug_log: LocalProxy[list[str]] = local("debug_log")
message_log: LocalProxy[list[LogMessageType]] = local("message_log")

lang: LocalProxy[str] = local("lang")

if TYPE_CHECKING:  # pragma: no cover
	# trick because some type checkers fail to follow "RedisWrapper", etc (written as string literal)
	# trough a generic wrapper; seems to be a bug
	db: PyMariaDBDatabase | MariaDBDatabase | PostgresDatabase | SQLiteDatabase
	qb: MariaDB | Postgres
	conf: ConfType
	form_dict: FormDict
	request: Request
	job: JobMetaType
	response: ResponseDict
	session: SessionType
	user: str
	flags: FlagsDict

	error_log: list[dict[str, str]]
	debug_log: list[str]
	message_log: list[LogMessageType]

	lang: str


def init(site: str, sites_path: str = ".", new_site: bool = False, force: bool = False) -> None:
	"""Initialize frappe for the current site. Reset thread locals `frappe.local`"""
	if getattr(local, "initialised", None) and not force:
		return

	local.error_log = []
	local.message_log = []
	local.debug_log = []
	local.flags = _dict(
		{
			"currently_saving": [],
			"redirect_location": "",
			"in_install_db": False,
			"in_install_app": False,
			"in_import": False,
			"in_test": in_test,
			"mute_messages": False,
			"ignore_links": False,
			"mute_emails": False,
			"has_dataurl": False,
			"new_site": new_site,
			"read_only": False,
		}
	)
	local.locked_documents = []
	local.test_objects = defaultdict(list)

	local.site = site
	local.site_name = site  # implicitly scopes bench
	local.sites_path = sites_path
	site_path = os.path.join(sites_path, site)
	local.site_path = site_path
	local.all_apps = None

	local.request_ip = None
	local.response = _dict({"docs": []})
	local.response_headers = Headers()
	local.task_id = None

	local.conf = get_site_config(sites_path=sites_path, site_path=site_path, cached=bool(frappe.request))
	local.lang = local.conf.lang or "en"

	local.module_app = None
	local.app_modules = None

	local.user = None
	local.user_perms = None
	local.session = None
	local.role_permissions = {}
	local.valid_columns = {}
	local.new_doc_templates = {}

	local.request_cache = defaultdict(dict)
	local.jenv = None
	local.jloader = None
	local.cache = {}
	local.form_dict = _dict()
	local.preload_assets = {"style": [], "script": [], "icons": []}
	local.session = _dict()
	local.dev_server = _dev_server  # only for backwards compatibility
	local.qb = get_query_builder(local.conf.db_type)
	if not cache or not client_cache:
		setup_redis_cache_connection()

	setup_module_map(include_all_apps=not (frappe.request or frappe.job or frappe.flags.in_migrate))

	local.initialised = True


def connect(site: str | None = None, db_name: str | None = None, set_admin_as_user: bool = True) -> None:
	"""Connect to site database instance.

	:param site: (Deprecated) If site is given, calls `frappe.init`.
	:param db_name: (Deprecated) Optional. Will use from `site_config.json`.
	:param set_admin_as_user: Set Administrator as current user.
	"""
	from frappe.database import get_db

	if site:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v17",
			"Calling frappe.connect with the site argument is deprecated and will be removed in next major version. "
			"Instead, explicitly invoke frappe.init(site) prior to calling frappe.connect(), if initializing the site is necessary.",
		)
		init(site)

	if db_name:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v17",
			"Calling frappe.connect with the db_name argument is deprecated and will be removed in next major version. "
			"Instead, explicitly invoke frappe.init(site) with the right config prior to calling frappe.connect(), if necessary.",
		)

	conf = local.conf
	db_user = conf.db_user or db_name
	db_name_ = conf.db_name or db_name
	db_password = conf.db_password

	assert db_name_, "site must be fully initialized, db_name missing"

	if frappe.conf.db_type in ("mariadb", "postgres"):
		assert db_user, "site must be fully initialized, db_user missing"
		assert db_password, "site must be fully initialized, db_password missing"

	local.db = get_db(
		socket=conf.db_socket,
		host=conf.db_host,
		port=conf.db_port,
		user=db_user,
		password=db_password,
		cur_db_name=db_name_,
	)

	if set_admin_as_user:
		set_user("Administrator")


def connect_replica() -> bool:
	from frappe.database import get_db

	if hasattr(local, "replica_db") and hasattr(local, "primary_db"):
		return False

	user = local.conf.db_user
	password = local.conf.db_password
	port = local.conf.replica_db_port

	if local.conf.different_credentials_for_replica:
		user = local.conf.replica_db_user or local.conf.replica_db_name
		password = local.conf.replica_db_password

	local.replica_db = get_db(
		socket=None,
		host=local.conf.replica_host,
		port=port,
		user=user,
		password=password,
		cur_db_name=local.conf.db_name,
	)

	# swap db connections
	local.primary_db = local.db
	local.db = local.replica_db

	if hasattr(frappe.local, "_recorder"):
		frappe.local._recorder._patch_sql(local.db)

	return True


class init_site:
	def __init__(self, site=None):
		"""If site is None, initialize it for empty site ('') to load common_site_config.json"""
		self.site = site or ""

	def __enter__(self):
		init(self.site)
		return local

	def __exit__(self, type, value, traceback):
		destroy()


def destroy():
	"""Closes connection and releases werkzeug local."""
	if db:
		db.close()

	release_local(local)


_redis_init_lock = threading.Lock()


def setup_redis_cache_connection():
	"""Defines `frappe.cache` as `RedisWrapper` instance"""
	from frappe.utils.redis_wrapper import ClientCache, setup_cache

	global cache
	global client_cache

	with _redis_init_lock:
		# We need to check again since someone else might have setup connection before us.
		if not cache:
			cache = setup_cache()
			client_cache = ClientCache()


def errprint(msg: str) -> None:
	"""Log error. This is sent back as `exc` in response.

	:param msg: Message."""
	msg = as_unicode(msg)
	if not request or ("cmd" not in local.form_dict) or conf.developer_mode:
		print(msg)

	error_log.append({"exc": msg})


def print_sql(enable: bool = True) -> None:
	if not local.conf.allow_tests:
		frappe.throw("`frappe.print_sql` only works with `allow_tests` site config enabled.")

	client_cache.set_value("flag_print_sql", enable)


def log(msg: str) -> None:
	"""Add to `debug_log`

	:param msg: Message."""
	print(msg, file=sys.stderr)
	debug_log.append(as_unicode(msg))


def set_user(username: str):
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
	local.user_perms = None


def get_user():
	from frappe.utils.user import UserPermissions

	if not local.user_perms:
		local.user_perms = UserPermissions(local.session.user)
	return local.user_perms


def get_roles(username=None) -> list[str]:
	"""Return roles of current user."""
	if not local.session or not local.session.user:
		return ["Guest"]
	import frappe.permissions

	return frappe.permissions.get_roles(username or local.session.user)


def get_request_header(key, default=None):
	"""Return HTTP request header.

	:param key: HTTP header key.
	:param default: Default value."""
	return request.headers.get(key, default)


whitelisted: set[Callable] = set()
guest_methods: set[Callable] = set()
xss_safe_methods: set[Callable] = set()
allowed_http_methods_for_whitelisted_func: dict[Callable, list[str]] = {}


def _in_request_or_test():
	"""
	Internal

	Used by whitelist to determine whether type hints should be validated or not
	"""

	return getattr(local, "request", None) or in_test


def whitelist(allow_guest=False, xss_safe=False, methods=None):
	"""
	Decorator for whitelisting a function and making it accessible via HTTP.
	Standard request will be `/api/method/[path.to.method]`

	:param allow_guest: Allow non logged-in user to access this method.
	:param methods: Allowed http method to access the method.

	Use as:

	        @frappe.whitelist()
	        def myfunc(param1, param2):
	                pass
	"""

	if not methods:
		methods = ["GET", "POST", "PUT", "DELETE"]

	def innerfn(fn):
		from frappe.utils.typing_validations import validate_argument_types

		global whitelisted, guest_methods, xss_safe_methods, allowed_http_methods_for_whitelisted_func

		# validate argument types if request is present or in test context
		fn = validate_argument_types(fn, apply_condition=_in_request_or_test)

		whitelisted.add(fn)
		allowed_http_methods_for_whitelisted_func[fn] = methods

		if allow_guest:
			guest_methods.add(fn)

			if xss_safe:
				xss_safe_methods.add(fn)

		return fn

	return innerfn


def is_whitelisted(method):
	from frappe.utils import sanitize_html

	is_guest = session["user"] == "Guest"
	if method not in whitelisted or (is_guest and method not in guest_methods):
		summary = _("You are not permitted to access this resource. Login to access")
		detail = _("Function {0} is not whitelisted.").format(bold(f"{method.__module__}.{method.__name__}"))
		msg = f"<details><summary>{summary}</summary>{detail}</details>"
		throw(msg, PermissionError, title=_("Method Not Allowed"))

	if is_guest and method not in xss_safe_methods:
		# strictly sanitize form_dict
		# escapes html characters like <> except for predefined tags like a, b, ul etc.
		for key, value in form_dict.items():
			if isinstance(value, str):
				form_dict[key] = sanitize_html(value)


def read_only():
	def innfn(fn):
		@functools.wraps(fn)
		def wrapper_fn(*args, **kwargs):
			# frappe.read_only could be called from nested functions, in such cases don't swap the
			# connection again.
			switched_connection = False
			if conf.read_from_replica:
				switched_connection = connect_replica()

			try:
				retval = fn(*args, **get_newargs(fn, kwargs))
			finally:
				if switched_connection and hasattr(local, "primary_db"):
					local.db.close()
					local.db = local.primary_db

			return retval

		return wrapper_fn

	return innfn


def write_only():
	# if replica connection exists, we have to replace it momentarily with the primary connection
	def innfn(fn):
		def wrapper_fn(*args, **kwargs):
			primary_db = getattr(local, "primary_db", None)
			replica_db = getattr(local, "replica_db", None)
			in_read_only = getattr(local, "db", None) != primary_db

			# switch to primary connection
			if in_read_only and primary_db:
				local.db = local.primary_db

			try:
				retval = fn(*args, **get_newargs(fn, kwargs))
			finally:
				# switch back to replica connection
				if in_read_only and replica_db:
					local.db = replica_db

			return retval

		return wrapper_fn

	return innfn


def only_for(roles: list[str] | tuple[str] | str, message=False):
	"""
	Raises `frappe.PermissionError` if the user does not have any of the permitted roles.

	:param roles: Permitted role(s)
	"""

	if local.session.user == "Administrator":
		return

	if isinstance(roles, str):
		roles = (roles,)

	if set(roles).isdisjoint(get_roles()):
		if not message:
			raise PermissionError

		throw(
			_("This action is only allowed for {}").format(
				", ".join(bold(_(role)) for role in roles),
			),
			PermissionError,
			_("Not Permitted"),
		)


def get_domain_data(module):
	try:
		domain_data = get_hooks("domains")
		if module in domain_data:
			return _dict(get_attr(get_hooks("domains")[module][0] + ".data"))
		else:
			return _dict()
	except ImportError:
		if in_test:
			return _dict()
		else:
			raise


def only_has_select_perm(doctype, user=None, ignore_permissions=False):
	if ignore_permissions:
		return False

	from frappe.permissions import get_role_permissions

	user = user or local.session.user
	permissions = get_role_permissions(doctype, user=user)

	return permissions.get("select") and not permissions.get("read")


def has_permission(
	doctype=None,
	ptype="read",
	doc=None,
	user=None,
	throw=False,
	*,
	parent_doctype=None,
	debug=False,
	ignore_share_permissions=False,
):
	"""
	Return True if the user has permission `ptype` for given `doctype` or `doc`.

	Raise `frappe.PermissionError` if user isn't permitted and `throw` is truthy

	:param doctype: DocType for which permission is to be check.
	:param ptype: Permission type (`read`, `write`, `create`, `submit`, `cancel`, `amend`). Default: `read`.
	:param doc: [optional] Checks User permissions for given doc.
	:param user: [optional] Check for given user. Default: current user.
	:param parent_doctype: Required when checking permission for a child DocType (unless doc is specified).
	"""
	import frappe.permissions

	if not doctype and doc:
		doctype = doc.doctype

	out = frappe.permissions.has_permission(
		doctype,
		ptype,
		doc=doc,
		user=user,
		print_logs=throw,
		parent_doctype=parent_doctype,
		debug=debug,
		ignore_share_permissions=ignore_share_permissions,
	)

	if throw and not out:
		if doc:
			frappe.permissions.check_doctype_permission(doctype, ptype)

		document_label = f"{_(doctype)} {doc if isinstance(doc, str) else doc.name}" if doc else _(doctype)
		frappe.flags.error_message = _("No permission for {0}").format(document_label)
		raise frappe.PermissionError

	return out


def has_website_permission(doc=None, ptype="read", user=None, verbose=False, doctype=None):
	"""Raises `frappe.PermissionError` if not permitted.

	:param doctype: DocType for which permission is to be check.
	:param ptype: Permission type (`read`, `write`, `create`, `submit`, `cancel`, `amend`). Default: `read`.
	:param doc: Checks User permissions for given doc.
	:param user: [optional] Check for given user. Default: current user."""

	if not user:
		user = session.user

	if doc:
		if isinstance(doc, str):
			doc = get_lazy_doc(doctype, doc)

		doctype = doc.doctype

		if doc.flags.ignore_permissions:
			return True

		# check permission in controller
		if hasattr(doc, "has_website_permission"):
			return doc.has_website_permission(ptype, user, verbose=verbose)

	hooks = (get_hooks("has_website_permission") or {}).get(doctype, [])
	if hooks:
		for method in hooks:
			result = call(method, doc=doc, ptype=ptype, user=user, verbose=verbose)
			# if even a single permission check is Falsy
			if not result:
				return False

		# else it is Truthy
		return True

	else:
		return False


def is_table(doctype: str) -> bool:
	"""Return True if `istable` property (indicating child Table) is set for given DocType."""
	key = "is_table"
	tables = client_cache.get_value(key)
	if tables is None:
		tables = db.get_values("DocType", filters={"istable": 1}, order_by=None, pluck=True)
		client_cache.set_value(key, tables)
	return doctype in tables


def get_precision(
	doctype: str, fieldname: str, currency: str | None = None, doc: Optional["Document"] = None
) -> int:
	"""Get precision for a given field"""
	from frappe.model.meta import get_field_precision

	return get_field_precision(get_meta(doctype).get_field(fieldname), doc, currency)


def generate_hash(txt: str | None = None, length: int = 56) -> str:
	"""Generate random hash using best available randomness source."""
	import math
	import secrets

	if txt:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown", "v17", "The `txt` parameter is deprecated and will be removed in a future release."
		)

	return secrets.token_hex(math.ceil(length / 2))[:length]


def set_value(doctype, docname, fieldname, value=None):
	"""Set document value. Calls `frappe.client.set_value`"""
	import frappe.client

	return frappe.client.set_value(doctype, docname, fieldname, value)


def get_meta_module(doctype):
	import frappe.modules

	return frappe.modules.load_doctype_module(doctype)


def delete_doc(
	doctype: str | None = None,
	name: str | dict | None = None,
	force: bool = False,
	ignore_doctypes: list[str] | None = None,
	for_reload: bool = False,
	ignore_permissions: bool = False,
	flags: _dict | None = None,
	ignore_on_trash: bool = False,
	ignore_missing: bool = True,
	delete_permanently: bool = False,
):
	"""Delete a document. Calls `frappe.model.delete_doc.delete_doc`.

	:param doctype: DocType of document to be delete.
	:param name: Name of document to be delete.
	:param force: Allow even if document is linked. Warning: This may lead to data integrity errors.
	:param ignore_doctypes: Ignore if child table is one of these.
	:param for_reload: Call `before_reload` trigger before deleting.
	:param ignore_permissions: Ignore user permissions.
	:param delete_permanently: Do not create a Deleted Document for the document."""
	import frappe.model.delete_doc

	return frappe.model.delete_doc.delete_doc(
		doctype,
		name,
		force,
		ignore_doctypes,
		for_reload,
		ignore_permissions,
		flags,
		ignore_on_trash,
		ignore_missing,
		delete_permanently,
	)


def reload_doctype(doctype, force=False, reset_permissions=False):
	"""Reload DocType from model (`[module]/[doctype]/[name]/[name].json`) files."""
	reload_doc(
		scrub(db.get_value("DocType", doctype, "module")),
		"doctype",
		scrub(doctype),
		force=force,
		reset_permissions=reset_permissions,
	)


def reload_doc(
	module: str,
	dt: str | None = None,
	dn: str | None = None,
	force: bool = False,
	reset_permissions: bool = False,
):
	"""Reload Document from model (`[module]/[doctype]/[name]/[name].json`) files.

	:param module: Module name.
	:param dt: DocType name.
	:param dn: Document name.
	:param force: Reload even if `modified` timestamp matches.
	"""

	import frappe.modules

	return frappe.modules.reload_doc(module, dt, dn, force=force, reset_permissions=reset_permissions)


@whitelist(methods=["POST", "PUT"])
def rename_doc(
	doctype: str,
	old: str | int,
	new: str | int,
	force: bool = False,
	merge: bool = False,
	*,
	ignore_if_exists: bool = False,
	show_alert: bool = True,
	rebuild_search: bool = True,
) -> str:
	"""
	Renames a doc(dt, old) to doc(dt, new) and updates all linked fields of type "Link"

	Calls `frappe.model.rename_doc.rename_doc`
	"""

	from frappe.model.rename_doc import rename_doc

	return rename_doc(
		doctype=doctype,
		old=old,
		new=new,
		force=force,
		merge=merge,
		ignore_if_exists=ignore_if_exists,
		show_alert=show_alert,
		rebuild_search=rebuild_search,
	)


def get_module(modulename: str):
	"""Return a module object for given Python module name using `importlib.import_module`."""
	return importlib.import_module(modulename)


def scrub(txt: str) -> str:
	"""Return sluggified string. e.g. `Sales Order` becomes `sales_order`."""
	return cstr(txt).replace(" ", "_").replace("-", "_").lower()


def unscrub(txt: str) -> str:
	"""Return titlified string. e.g. `sales_order` becomes `Sales Order`."""
	return txt.replace("_", " ").replace("-", " ").title()


def get_module_path(module, *joins):
	"""Get the path of the given module name.

	:param module: Module name.
	:param *joins: Join additional path elements using `os.path.join`."""
	from frappe.modules.utils import get_module_app

	app = get_module_app(module)
	return get_pymodule_path(app + "." + scrub(module), *joins)


def get_app_path(app_name, *joins):
	"""Return path of given app.

	:param app: App name.
	:param *joins: Join additional path elements using `os.path.join`."""
	return get_pymodule_path(app_name, *joins)


def get_app_source_path(app_name, *joins):
	"""Return source path of given app.

	:param app: App name.
	:param *joins: Join additional path elements using `os.path.join`."""
	return get_app_path(app_name, "..", *joins)


def get_site_path(*joins):
	"""Return path of current site.

	:param *joins: Join additional path elements using `os.path.join`."""
	from os.path import join

	return join(local.site_path, *joins)


def get_pymodule_path(modulename, *joins):
	"""Return path of given Python module name.

	:param modulename: Python module name.
	:param *joins: Join additional path elements using `os.path.join`."""
	from os.path import abspath, dirname, join

	if "public" not in joins:
		joins = [scrub(part) for part in joins]

	return abspath(join(dirname(get_module(scrub(modulename)).__file__ or ""), *joins))


def get_module_list(app_name):
	"""Get list of modules for given all via `app/modules.txt`."""
	return get_file_items(get_app_path(app_name, "modules.txt"))


def get_all_apps(with_internal_apps=True, sites_path=None):
	"""Get list of all apps via `sites/apps.txt`."""
	if not sites_path:
		sites_path = local.sites_path

	apps = get_file_items(os.path.join(sites_path, "apps.txt"), raise_not_found=True)

	if with_internal_apps:
		for app in get_file_items(os.path.join(local.site_path, "apps.txt")):
			if app not in apps:
				apps.append(app)

	if "frappe" in apps:
		apps.remove("frappe")
	apps.insert(0, "frappe")

	return apps


@request_cache
def get_installed_apps(*, _ensure_on_bench: bool = False) -> list[str]:
	"""
	Get list of installed apps in current site.

	:param _ensure_on_bench: Only return apps that are present on bench.
	"""
	if getattr(flags, "in_install_db", True):
		return []

	if not db:
		connect()

	installed = orjson.loads(db.get_global("installed_apps") or "[]")

	if _ensure_on_bench:
		all_apps = cache.get_value("all_apps", get_all_apps)
		installed = [app for app in installed if app in all_apps]

	return installed


def get_doc_hooks():
	"""Return hooked methods for given doc. Expand the dict tuple if required."""
	if not hasattr(local, "doc_events_hooks"):
		hooks = get_hooks("doc_events", {})
		out = {}
		for key, value in hooks.items():
			if isinstance(key, tuple):
				for doctype in key:
					append_hook(out, doctype, value)
			else:
				append_hook(out, key, value)

		local.doc_events_hooks = out

	return local.doc_events_hooks


def _load_app_hooks(app_name: str | None = None):
	import types

	hooks = {}
	apps = [app_name] if app_name else get_installed_apps(_ensure_on_bench=True)

	for app in apps:
		try:
			app_hooks = get_module(f"{app}.hooks")
		except ImportError as e:
			if local.flags.in_install_app:
				# if app is not installed while restoring
				# ignore it
				pass
			print(f'Could not find app "{app}": \n{e}')
			raise

		def _is_valid_hook(obj):
			return not isinstance(obj, types.ModuleType | types.FunctionType | type)

		for key, value in inspect.getmembers(app_hooks, predicate=_is_valid_hook):
			if not key.startswith("_"):
				append_hook(hooks, key, value)
	return hooks


_request_cached_load_app_hooks = request_cache(_load_app_hooks)
_site_cached_load_app_hooks = site_cache(_load_app_hooks)


def get_hooks(
	hook: str | None = None, default: Any | None = "_KEEP_DEFAULT_LIST", app_name: str | None = None
) -> _dict:
	"""Get hooks via `app/hooks.py`

	:param hook: Name of the hook. Will gather all hooks for this name and return as a list.
	:param default: Default if no hook found.
	:param app_name: Filter by app."""

	if app_name:
		hooks = _request_cached_load_app_hooks(app_name)
	elif local.conf.developer_mode:
		hooks = _site_cached_load_app_hooks()
	else:
		hooks = client_cache.get_value("app_hooks")
		if hooks is None:
			hooks = _load_app_hooks()
			client_cache.set_value("app_hooks", hooks)

	if hook:
		return hooks.get(hook, ([] if default == "_KEEP_DEFAULT_LIST" else default))

	return _dict(hooks)


def append_hook(target, key, value):
	"""appends a hook to the the target dict.

	If the hook key, exists, it will make it a key.

	If the hook value is a dict, like doc_events, it will
	listify the values against the key.
	"""
	if isinstance(value, dict):
		# dict? make a list of values against each key
		target.setdefault(key, {})
		for inkey in value:
			append_hook(target[key], inkey, value[inkey])
	else:
		# make a list
		target.setdefault(key, [])
		if not isinstance(value, list):
			value = [value]
		target[key].extend(value)


def setup_module_map(include_all_apps: bool = True) -> None:
	"""
	Function to rebuild map of all modules

	:param: include_all_apps: Include all apps on bench, or just apps installed on the site.
	:return: Nothing
	"""
	if include_all_apps:
		app_modules = cache.get_value("app_modules")
	else:
		app_modules = client_cache.get_value("installed_app_modules")

	if not app_modules:
		app_modules = {}

		if include_all_apps:
			apps = get_all_apps(with_internal_apps=True)
		else:
			apps = get_installed_apps(_ensure_on_bench=True)

		for app in apps:
			app_modules.setdefault(app, [])
			for module in get_module_list(app):
				module = scrub(module)
				app_modules[app].append(module)

		if include_all_apps:
			cache.set_value("app_modules", app_modules)
		else:
			client_cache.set_value("installed_app_modules", app_modules)

	# Init module_app (reverse mapping)
	module_app = {}
	for app, modules in app_modules.items():
		for module in modules:
			if module in module_app:
				warnings.warn(
					f"WARNING: module `{module}` found in apps `{module_app[module]}` and `{app}`",
					stacklevel=1,
				)
			module_app[module] = app

	local.app_modules = app_modules
	local.module_app = module_app


def get_file_items(path, raise_not_found=False, ignore_empty_lines=True):
	"""Return items from text file as a list. Ignore empty lines."""
	import frappe.utils

	content = read_file(path, raise_not_found=raise_not_found)
	if content:
		content = frappe.utils.strip(content)

		return [
			p.strip()
			for p in content.splitlines()
			if (not ignore_empty_lines) or (p.strip() and not p.startswith("#"))
		]
	else:
		return []


def get_file_json(path):
	"""Read a file and return parsed JSON object."""
	with open(path) as f:
		return json.load(f)


def read_file(path, raise_not_found=False, as_base64=False):
	"""Open a file and return its content as Unicode or Base64 string."""
	if isinstance(path, str):
		path = path.encode("utf-8")

	if os.path.exists(path):
		if as_base64:
			import base64

			with open(path, "rb") as f:
				content = f.read()
				return base64.b64encode(content).decode("utf-8")
		else:
			with open(path) as f:
				content = f.read()
				return as_unicode(content)
	elif raise_not_found:
		raise OSError(f"{path} Not Found")
	else:
		return None


def get_attr(method_string: str) -> Any:
	"""Get python method object from its name."""
	app_name = method_string.split(".", 1)[0]
	if not local.flags.in_uninstall and not local.flags.in_install and app_name not in get_installed_apps():
		throw(_("App {0} is not installed").format(app_name), AppNotInstalledError)

	modulename = ".".join(method_string.split(".")[:-1])
	methodname = method_string.split(".")[-1]
	return getattr(get_module(modulename), methodname)


def call(fn: str | Callable, *args, **kwargs):
	"""Call a function and match arguments."""
	if isinstance(fn, str):
		fn = get_attr(fn)

	newargs = get_newargs(fn, kwargs)

	return fn(*args, **newargs)


@functools.lru_cache
def _get_cached_signature_params(fn: Callable) -> tuple[dict[str, Any], bool]:
	"""
	Get cached parameters for a function.
	Returns a dictionary of parameters and a boolean indicating if the function has **kwargs.
	"""

	signature = inspect.signature(fn)

	# if function has any **kwargs parameter that capture arbitrary keyword arguments
	# Ref: https://docs.python.org/3/library/inspect.html#inspect.Parameter.kind
	variable_kwargs_exist = any(
		parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
	)

	return dict(signature.parameters), variable_kwargs_exist


def get_newargs(fn: Callable, kwargs: dict[str, Any]) -> dict[str, Any]:
	"""Remove any kwargs that are not supported by the function.

	Example:
	        >>> def fn(a=1, b=2):
	        ...     pass

	        >>> get_newargs(fn, {"a": 2, "c": 1})
	                {"a": 2}
	"""

	parameters, variable_kwargs_exist = _get_cached_signature_params(fn)
	newargs = (
		kwargs.copy()
		if variable_kwargs_exist
		else {key: value for key, value in kwargs.items() if key in parameters}
	)

	# WARNING: This behaviour is now  part of business logic in places, never remove.
	newargs.pop("ignore_permissions", None)
	newargs.pop("flags", None)

	return newargs


def make_property_setter(
	args, ignore_validate=False, validate_fields_for_doctype=True, is_system_generated=True
):
	"""Create a new **Property Setter** (for overriding DocType and DocField properties).

	If doctype is not specified, it will create a property setter for all fields with the
	given fieldname"""
	args = _dict(args)
	if not args.doctype_or_field:
		args.doctype_or_field = "DocField"
		if not args.property_type:
			args.property_type = (
				db.get_value("DocField", {"parent": "DocField", "fieldname": args.property}, "fieldtype")
				or "Data"
			)

	if not args.doctype:
		DocField_doctype = qb.DocType("DocField")
		doctype_list = (
			qb.from_(DocField_doctype)
			.select(DocField_doctype.parent)
			.where(DocField_doctype.fieldname == args.fieldname)
			.distinct()
		).run(pluck=True)

	else:
		doctype_list = [args.doctype]

	for doctype in doctype_list:
		if not args.property_type:
			args.property_type = (
				db.get_value("DocField", {"parent": doctype, "fieldname": args.fieldname}, "fieldtype")
				or "Data"
			)

		ps = get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": args.doctype_or_field,
				"doc_type": doctype,
				"field_name": args.fieldname,
				"row_name": args.row_name,
				"property": args.property,
				"value": args.value,
				"property_type": args.property_type or "Data",
				"is_system_generated": is_system_generated,
				"__islocal": 1,
			}
		)
		ps.flags.ignore_validate = ignore_validate
		ps.flags.validate_fields_for_doctype = validate_fields_for_doctype
		ps.validate_fieldtype_change()
		ps.insert()


def import_doc(path):
	"""Import a file using Data Import."""
	from frappe.core.doctype.data_import.data_import import import_doc

	import_doc(path)


def respond_as_web_page(
	title,
	html,
	success=None,
	http_status_code=None,
	context=None,
	indicator_color=None,
	primary_action="/",
	primary_label=None,
	fullpage=False,
	width=None,
	template="message",
):
	"""Send response as a web page with a message rather than JSON. Used to show permission errors etc.

	:param title: Page title and heading.
	:param message: Message to be shown.
	:param success: Alert message.
	:param http_status_code: HTTP status code
	:param context: web template context
	:param indicator_color: color of indicator in title
	:param primary_action: route on primary button (default is `/`)
	:param primary_label: label on primary button (default is "Home")
	:param fullpage: hide header / footer
	:param width: Width of message in pixels
	:param template: Optionally pass view template
	"""
	local.message_title = title
	local.message = html
	local.response["type"] = "page"
	local.response["route"] = template
	local.no_cache = 1

	if http_status_code:
		local.response["http_status_code"] = http_status_code

	if not context:
		context = {}

	if not indicator_color:
		if success:
			indicator_color = "green"
		elif http_status_code and http_status_code > 300:
			indicator_color = "red"
		else:
			indicator_color = "blue"

	context["indicator_color"] = indicator_color
	context["primary_label"] = primary_label
	context["primary_action"] = primary_action
	context["error_code"] = http_status_code
	context["fullpage"] = fullpage
	if width:
		context["card_width"] = width

	local.response["context"] = context


def redirect(url):
	"""Raise a 301 redirect to url"""
	from frappe.exceptions import Redirect

	flags.redirect_location = url
	raise Redirect


def redirect_to_message(title, html, http_status_code=None, context=None, indicator_color=None):
	"""Redirects to /message?id=random
	Similar to respond_as_web_page, but used to 'redirect' and show message pages like success, failure, etc. with a detailed message

	:param title: Page title and heading.
	:param message: Message to be shown.
	:param http_status_code: HTTP status code.

	Example Usage:
	        frappe.redirect_to_message(_('Thank you'), "<div><p>You will receive an email at test@example.com</p></div>")

	"""

	message_id = generate_hash(length=8)
	message = {"context": context or {}, "http_status_code": http_status_code or 200}
	message["context"].update({"header": title, "title": title, "message": html})

	if indicator_color:
		message["context"].update({"indicator_color": indicator_color})

	cache.set_value(f"message_id:{message_id}", message, expires_in_sec=60)
	location = f"/message?id={message_id}"

	if not getattr(local, "is_ajax", False):
		local.response["type"] = "redirect"
		local.response["location"] = location

	else:
		return location


def build_match_conditions(doctype, as_condition=True):
	"""Return match (User permissions) for given doctype as list or SQL."""
	import frappe.desk.reportview

	return frappe.desk.reportview.build_match_conditions(doctype, as_condition=as_condition)


def get_list(doctype, *args, **kwargs):
	"""List database query via `frappe.model.db_query`. Will also check for permissions.

	:param doctype: DocType on which query is to be made.
	:param fields: List of fields or `*`.
	:param filters: List of filters (see example).
	:param order_by: Order By e.g. `creation desc`.
	:param limit_start: Start results at record #. Default 0.
	:param limit_page_length: No of records in the page. Default 20.

	Example usage:

	        # simple dict filter
	        frappe.get_list("ToDo", fields=["name", "description"], filters = {"owner":"test@example.com"})

	        # filter as a list of lists
	        frappe.get_list("ToDo", fields="*", filters = [["modified", ">", "2014-01-01"]])
	"""
	import frappe.model.db_query

	return frappe.model.db_query.DatabaseQuery(doctype).execute(*args, **kwargs)


def get_all(doctype, *args, **kwargs):
	"""List database query via `frappe.model.db_query`. Will **not** check for permissions.
	Parameters are same as `frappe.get_list`

	:param doctype: DocType on which query is to be made.
	:param fields: List of fields or `*`. Default is: `["name"]`.
	:param filters: List of filters (see example).
	:param order_by: Order By e.g. `creation desc`.
	:param limit_start: Start results at record #. Default 0.
	:param limit_page_length: No of records in the page. Default 20.

	Example usage:

	        # simple dict filter
	        frappe.get_all("ToDo", fields=["name", "description"], filters = {"owner":"test@example.com"})

	        # filter as a list of lists
	        frappe.get_all("ToDo", fields=["*"], filters = [["modified", ">", "2014-01-01"]])
	"""
	kwargs["ignore_permissions"] = True
	if "limit_page_length" not in kwargs:
		kwargs["limit_page_length"] = 0
	return get_list(doctype, *args, **kwargs)


def get_value(*args, **kwargs):
	"""Return a document property or list of properties.

	Alias for `frappe.db.get_value`

	:param doctype: DocType name.
	:param filters: Filters like `{"x":"y"}` or name of the document. `None` if Single DocType.
	:param fieldname: Column name.
	:param ignore: Don't raise exception if table, column is missing.
	:param as_dict: Return values as dict.
	:param debug: Print query in error log.
	"""
	return local.db.get_value(*args, **kwargs)


def as_json(obj: dict | list, indent=1, separators=None, ensure_ascii=True) -> str:
	"""Return the JSON string representation of the given `obj`."""
	from frappe.utils.response import json_handler

	if separators is None:
		separators = (",", ": ")

	try:
		return json.dumps(
			obj,
			indent=indent,
			sort_keys=True,
			default=json_handler,
			separators=separators,
			ensure_ascii=ensure_ascii,
		)
	except TypeError:
		# this would break in case the keys are not all os "str" type - as defined in the JSON
		# adding this to ensure keys are sorted (expected behaviour)
		sorted_obj = dict(sorted(obj.items(), key=lambda kv: str(kv[0])))
		return json.dumps(
			sorted_obj,
			indent=indent,
			default=json_handler,
			separators=separators,
			ensure_ascii=ensure_ascii,
		)


def are_emails_muted():
	return flags.mute_emails or cint(conf.get("mute_emails", 0))


from frappe.deprecation_dumpster import frappe_get_test_records as get_test_records


def task(**task_kwargs):
	def decorator_task(f):
		f.enqueue = lambda **fun_kwargs: enqueue(f, **task_kwargs, **fun_kwargs)
		return f

	return decorator_task


def get_doctype_app(doctype):
	def _get_doctype_app():
		doctype_module = local.db.get_value("DocType", doctype, "module")
		return local.module_app[scrub(doctype_module)]

	return local_cache("doctype_app", doctype, generator=_get_doctype_app)


loggers: dict[str, "Logger"] = {}
log_level: int | None = None


def logger(
	module=None, with_more_info=False, allow_site=True, filter=None, max_size=100_000, file_count=20
) -> "Logger":
	"""Return a python logger that uses StreamHandler."""
	from frappe.utils.logger import get_logger

	return get_logger(
		module=module,
		with_more_info=with_more_info,
		allow_site=allow_site,
		filter=filter,
		max_size=max_size,
		file_count=file_count,
	)


def get_desk_link(doctype, name, show_title_with_name=False):
	meta = get_meta(doctype)
	title = get_value(doctype, name, meta.get_title_field())

	if show_title_with_name and name != title:
		html = '<a href="/app/Form/{doctype}/{name}" style="font-weight: bold;">{doctype_local} {name}: {title_local}</a>'
	else:
		html = '<a href="/app/Form/{doctype}/{name}" style="font-weight: bold;">{doctype_local} {title_local}</a>'

	return html.format(doctype=doctype, name=name, doctype_local=_(doctype), title_local=_(title))


def get_website_settings(key):
	if not hasattr(local, "website_settings"):
		try:
			local.website_settings = client_cache.get_doc("Website Settings")
		except DoesNotExistError:
			clear_last_message()
			return

	return local.website_settings.get(key)


def get_active_domains():
	from frappe.core.doctype.domain_settings.domain_settings import get_active_domains

	return get_active_domains()


@request_cache
def is_setup_complete():
	setup_complete = False
	if not frappe.db.table_exists("Installed Application"):
		return setup_complete

	if all(frappe.get_all("Installed Application", {"has_setup_wizard": 1}, pluck="is_setup_complete")):
		setup_complete = True

	return setup_complete


@whitelist(allow_guest=True)
def ping():
	return "pong"


def validate_and_sanitize_search_inputs(fn):
	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		from frappe.desk.search import sanitize_searchfield

		kwargs.update(dict(zip(fn.__code__.co_varnames, args, strict=False)))
		sanitize_searchfield(kwargs["searchfield"])
		kwargs["start"] = cint(kwargs["start"])
		kwargs["page_len"] = cint(kwargs["page_len"])

		if kwargs["doctype"] and not db.exists("DocType", kwargs["doctype"]):
			return []

		return fn(**kwargs)

	return wrapper


def override_whitelisted_method(original_method: str) -> str:
	"""Return the last override or the original whitelisted method."""
	overrides = frappe.get_hooks("override_whitelisted_methods", {}).get(original_method, [])
	return overrides[-1] if overrides else original_method


# Backward compatibility
from frappe.utils.messages import *  # noqa: I001

import frappe._optimizations
from frappe.cache_manager import clear_cache, reset_metadata_version
from frappe.config import get_common_site_config, get_conf, get_site_config
from frappe.core.doctype.system_settings.system_settings import get_system_settings
from frappe.model.document import (
	get_doc,
	get_lazy_doc,
	copy_doc,
	new_doc,
	get_cached_doc,
	can_cache_doc,
	get_document_cache_key,
	clear_document_cache,
	get_cached_value,
	get_single_value,
	get_last_doc,
	get_single,
	_set_document_in_cache,
)
from frappe.model.meta import get_meta
from frappe.realtime import publish_progress, publish_realtime
from frappe.utils import get_traceback, mock, parse_json, safe_eval, create_folder
from frappe.utils.background_jobs import enqueue, enqueue_doc
from frappe.utils.error import log_error
from frappe.utils.formatters import format_value
from frappe.utils.print_utils import get_print, attach_print
from frappe.email import sendmail

# for backwards compatibility
format = format_value
delete_doc_if_exists = delete_doc

frappe._optimizations.optimize_all()
frappe._optimizations.register_fault_handler()
