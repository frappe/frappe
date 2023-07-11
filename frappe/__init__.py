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
import gc
import importlib
import inspect
import json
import os
import re
import unicodedata
import warnings
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, overload

import click
from werkzeug.local import Local, release_local

from frappe.query_builder import (
	get_qb_engine,
	get_query_builder,
	patch_query_aggregation,
	patch_query_execute,
)
from frappe.utils.caching import request_cache
from frappe.utils.data import cstr, sbool

# Local application imports
from .exceptions import *
from .utils.jinja import (
	get_email_from_template,
	get_jenv,
	get_jloader,
	get_template,
	render_template,
)
from .utils.lazy_loader import lazy_import

__version__ = "14.40.3"
__title__ = "Frappe Framework"

controllers = {}
local = Local()
STANDARD_USERS = ("Guest", "Administrator")

_dev_server = int(sbool(os.environ.get("DEV_SERVER", False)))
_qb_patched = {}
re._MAXCACHE = (
	50  # reduced from default 512 given we are already maintaining this on parent worker
)

_tune_gc = bool(os.environ.get("FRAPPE_TUNE_GC", False))

if _dev_server:
	warnings.simplefilter("always", DeprecationWarning)
	warnings.simplefilter("always", PendingDeprecationWarning)


class _dict(dict):
	"""dict like object that exposes keys as attributes"""

	__slots__ = ()
	__getattr__ = dict.get
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__
	__setstate__ = dict.update

	def __getstate__(self):
		return self

	def update(self, *args, **kwargs):
		"""update and return self -- the missing dict feature in python"""

		super().update(*args, **kwargs)
		return self

	def copy(self):
		return _dict(self)


def _(msg: str, lang: str | None = None, context: str | None = None) -> str:
	"""Returns translated string in current lang, if exists.
	Usage:
	        _('Change')
	        _('Change', context='Coins')
	"""
	from frappe.translate import get_all_translations
	from frappe.utils import is_html, strip_html_tags

	if not hasattr(local, "lang"):
		local.lang = lang or "en"

	if not lang:
		lang = local.lang

	non_translated_string = msg

	if is_html(msg):
		msg = strip_html_tags(msg)

	# msg should always be unicode
	msg = as_unicode(msg).strip()

	translated_string = ""

	all_translations = get_all_translations(lang)
	if context:
		string_key = f"{msg}:{context}"
		translated_string = all_translations.get(string_key)

	if not translated_string:
		translated_string = all_translations.get(msg)

	return translated_string or non_translated_string


def as_unicode(text: str, encoding: str = "utf-8") -> str:
	"""Convert to unicode if required"""
	if isinstance(text, str):
		return text
	elif text is None:
		return ""
	elif isinstance(text, bytes):
		return str(text, encoding)
	else:
		return str(text)


def get_lang_dict(fortype: str, name: str | None = None) -> dict[str, str]:
	"""Returns the translated language dict for the given type and name.

	:param fortype: must be one of `doctype`, `page`, `report`, `include`, `jsfile`, `boot`
	:param name: name of the document for which assets are to be returned."""
	from frappe.translate import get_dict

	return get_dict(fortype, name)


def set_user_lang(user: str, user_language: str | None = None) -> None:
	"""Guess and set user language for the session. `frappe.local.lang`"""
	from frappe.translate import get_user_lang

	local.lang = get_user_lang(user) or user_language


# local-globals

db = local("db")
qb = local("qb")
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

# This if block is never executed when running the code. It is only used for
# telling static code analyzer where to find dynamically defined attributes.
if TYPE_CHECKING:
	from frappe.database.mariadb.database import MariaDBDatabase
	from frappe.database.postgres.database import PostgresDatabase
	from frappe.model.document import Document
	from frappe.query_builder.builder import MariaDB, Postgres
	from frappe.utils.redis_wrapper import RedisWrapper

	db: MariaDBDatabase | PostgresDatabase
	qb: MariaDB | Postgres


# end: static analysis hack


def init(site: str, sites_path: str = ".", new_site: bool = False, force=False) -> None:
	"""Initialize frappe for the current site. Reset thread locals `frappe.local`"""
	if getattr(local, "initialised", None) and not force:
		return

	local.error_log = []
	local.message_log = []
	local.debug_log = []
	local.realtime_log = []
	local.flags = _dict(
		{
			"currently_saving": [],
			"redirect_location": "",
			"in_install_db": False,
			"in_install_app": False,
			"in_import": False,
			"in_test": False,
			"mute_messages": False,
			"ignore_links": False,
			"mute_emails": False,
			"has_dataurl": False,
			"new_site": new_site,
			"read_only": False,
		}
	)
	local.rollback_observers = []
	local.locked_documents = []
	local.before_commit = []
	local.test_objects = {}

	local.site = site
	local.sites_path = sites_path
	local.site_path = os.path.join(sites_path, site)
	local.all_apps = None

	local.request_ip = None
	local.response = _dict({"docs": []})
	local.task_id = None

	local.conf = _dict(get_site_config())
	local.lang = local.conf.lang or "en"

	local.module_app = None
	local.app_modules = None

	local.user = None
	local.user_perms = None
	local.session = None
	local.role_permissions = {}
	local.valid_columns = {}
	local.new_doc_templates = {}
	local.link_count = {}

	local.jenv = None
	local.jloader = None
	local.cache = {}
	local.document_cache = {}
	local.form_dict = _dict()
	local.preload_assets = {"style": [], "script": []}
	local.session = _dict()
	local.dev_server = _dev_server
	local.qb = get_query_builder(local.conf.db_type or "mariadb")
	local.qb.engine = get_qb_engine()
	setup_module_map()

	if not _qb_patched.get(local.conf.db_type):
		patch_query_execute()
		patch_query_aggregation()

	local.initialised = True


def connect(
	site: str | None = None, db_name: str | None = None, set_admin_as_user: bool = True
) -> None:
	"""Connect to site database instance.

	:param site: If site is given, calls `frappe.init`.
	:param db_name: Optional. Will use from `site_config.json`.
	:param set_admin_as_user: Set Administrator as current user.
	"""
	from frappe.database import get_db

	if site:
		init(site)

	local.db = get_db(user=db_name or local.conf.db_name)
	if set_admin_as_user:
		set_user("Administrator")


def connect_replica():
	from frappe.database import get_db

	user = local.conf.db_name
	password = local.conf.db_password
	port = local.conf.replica_db_port

	if local.conf.different_credentials_for_replica:
		user = local.conf.replica_db_name
		password = local.conf.replica_db_password

	local.replica_db = get_db(host=local.conf.replica_host, user=user, password=password, port=port)

	# swap db connections
	local.primary_db = local.db
	local.db = local.replica_db


def get_site_config(sites_path: str | None = None, site_path: str | None = None) -> dict[str, Any]:
	"""Returns `site_config.json` combined with `sites/common_site_config.json`.
	`site_config` is a set of site wide settings like database name, password, email etc."""
	config = {}

	sites_path = sites_path or getattr(local, "sites_path", None)
	site_path = site_path or getattr(local, "site_path", None)

	if sites_path:
		common_site_config = os.path.join(sites_path, "common_site_config.json")
		if os.path.exists(common_site_config):
			try:
				config.update(get_file_json(common_site_config))
			except Exception as error:
				click.secho("common_site_config.json is invalid", fg="red")
				print(error)

	if site_path:
		site_config = os.path.join(site_path, "site_config.json")
		if os.path.exists(site_config):
			try:
				config.update(get_file_json(site_config))
			except Exception as error:
				click.secho(f"{local.site}/site_config.json is invalid", fg="red")
				print(error)
		elif local.site and not local.flags.new_site:
			raise IncorrectSitePath(f"{local.site} does not exist")

	return _dict(config)


def get_conf(site: str | None = None) -> dict[str, Any]:
	if hasattr(local, "conf"):
		return local.conf

	else:
		# if no site, get from common_site_config.json
		with init_site(site):
			return local.conf


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


redis_server = None


def cache() -> "RedisWrapper":
	"""Returns redis connection."""
	global redis_server
	if not redis_server:
		from frappe.utils.redis_wrapper import RedisWrapper

		redis_server = RedisWrapper.from_url(conf.get("redis_cache") or "redis://localhost:11311")
	return redis_server


def get_traceback(with_context: bool = False) -> str:
	"""Returns error traceback."""
	from frappe.utils import get_traceback

	return get_traceback(with_context=with_context)


def errprint(msg: str) -> None:
	"""Log error. This is sent back as `exc` in response.

	:param msg: Message."""
	msg = as_unicode(msg)
	if not request or (not "cmd" in local.form_dict) or conf.developer_mode:
		print(msg)

	error_log.append({"exc": msg})


def print_sql(enable: bool = True) -> None:
	return cache().set_value("flag_print_sql", enable)


def log(msg: str) -> None:
	"""Add to `debug_log`.

	:param msg: Message."""
	if not request:
		if conf.get("logging") or False:
			print(repr(msg))

	debug_log.append(as_unicode(msg))


def msgprint(
	msg: str,
	title: str | None = None,
	raise_exception: bool | type[Exception] = False,
	as_table: bool = False,
	as_list: bool = False,
	indicator: Literal["blue", "green", "orange", "red", "yellow"] | None = None,
	alert: bool = False,
	primary_action: str = None,
	is_minimizable: bool = False,
	wide: bool = False,
) -> None:
	"""Print a message to the user (via HTTP response).
	Messages are sent in the `__server_messages` property in the
	response JSON and shown in a pop-up / modal.

	:param msg: Message.
	:param title: [optional] Message title. Default: "Message".
	:param raise_exception: [optional] Raise given exception and show message.
	:param as_table: [optional] If `msg` is a list of lists, render as HTML table.
	:param as_list: [optional] If `msg` is a list, render as un-ordered list.
	:param primary_action: [optional] Bind a primary server/client side action.
	:param is_minimizable: [optional] Allow users to minimize the modal
	:param wide: [optional] Show wide modal
	"""
	import inspect
	import sys

	from frappe.utils import strip_html_tags

	msg = safe_decode(msg)
	out = _dict(message=msg)

	@functools.lru_cache(maxsize=1024)
	def _strip_html_tags(message):
		return strip_html_tags(message)

	def _raise_exception():
		if raise_exception:
			if inspect.isclass(raise_exception) and issubclass(raise_exception, Exception):
				raise raise_exception(msg)
			else:
				raise ValidationError(msg)

	if flags.mute_messages:
		_raise_exception()
		return

	if as_table and type(msg) in (list, tuple):
		out.as_table = 1

	if as_list and type(msg) in (list, tuple):
		out.as_list = 1

	if sys.stdin and sys.stdin.isatty():
		if out.as_list:
			msg = [_strip_html_tags(msg) for msg in out.message]
		else:
			msg = _strip_html_tags(out.message)

	if flags.print_messages and out.message:
		print(f"Message: {_strip_html_tags(out.message)}")

	out.title = title or _("Message", context="Default title of the message dialog")

	if not indicator and raise_exception:
		indicator = "red"

	if indicator:
		out.indicator = indicator

	if is_minimizable:
		out.is_minimizable = is_minimizable

	if alert:
		out.alert = 1

	if raise_exception:
		out.raise_exception = 1

	if primary_action:
		out.primary_action = primary_action

	if wide:
		out.wide = wide

	message_log.append(json.dumps(out))

	if raise_exception and hasattr(raise_exception, "__name__"):
		local.response["exc_type"] = raise_exception.__name__

	_raise_exception()


def clear_messages():
	local.message_log = []


def get_message_log():
	log = []
	for msg_out in local.message_log:
		log.append(json.loads(msg_out))

	return log


def clear_last_message():
	if len(local.message_log) > 0:
		local.message_log = local.message_log[:-1]


def throw(
	msg: str,
	exc: type[Exception] = ValidationError,
	title: str | None = None,
	is_minimizable: bool = False,
	wide: bool = False,
	as_list: bool = False,
) -> None:
	"""Throw execption and show message (`msgprint`).

	:param msg: Message.
	:param exc: Exception class. Default `frappe.ValidationError`"""
	msgprint(
		msg,
		raise_exception=exc,
		title=title,
		indicator="red",
		is_minimizable=is_minimizable,
		wide=wide,
		as_list=as_list,
	)


def create_folder(path, with_init=False):
	"""Create a folder in the given path and add an `__init__.py` file (optional).

	:param path: Folder path.
	:param with_init: Create `__init__.py` in the new folder."""
	from frappe.utils import touch_file

	if not os.path.exists(path):
		os.makedirs(path)

		if with_init:
			touch_file(os.path.join(path, "__init__.py"))


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
	"""Returns roles of current user."""
	if not local.session or not local.session.user:
		return ["Guest"]
	import frappe.permissions

	return frappe.permissions.get_roles(username or local.session.user)


def get_request_header(key, default=None):
	"""Return HTTP request header.

	:param key: HTTP header key.
	:param default: Default value."""
	return request.headers.get(key, default)


def sendmail(
	recipients=None,
	sender="",
	subject="No Subject",
	message="No Message",
	as_markdown=False,
	delayed=True,
	reference_doctype=None,
	reference_name=None,
	unsubscribe_method=None,
	unsubscribe_params=None,
	unsubscribe_message=None,
	add_unsubscribe_link=1,
	attachments=None,
	content=None,
	doctype=None,
	name=None,
	reply_to=None,
	queue_separately=False,
	cc=None,
	bcc=None,
	message_id=None,
	in_reply_to=None,
	send_after=None,
	expose_recipients=None,
	send_priority=1,
	communication=None,
	retry=1,
	now=None,
	read_receipt=None,
	is_notification=False,
	inline_images=None,
	template=None,
	args=None,
	header=None,
	print_letterhead=False,
	with_container=False,
):
	"""Send email using user's default **Email Account** or global default **Email Account**.


	:param recipients: List of recipients.
	:param sender: Email sender. Default is current user or default outgoing account.
	:param subject: Email Subject.
	:param message: (or `content`) Email Content.
	:param as_markdown: Convert content markdown to HTML.
	:param delayed: Send via scheduled email sender **Email Queue**. Don't send immediately. Default is true
	:param send_priority: Priority for Email Queue, default 1.
	:param reference_doctype: (or `doctype`) Append as communication to this DocType.
	:param reference_name: (or `name`) Append as communication to this document name.
	:param unsubscribe_method: Unsubscribe url with options email, doctype, name. e.g. `/api/method/unsubscribe`
	:param unsubscribe_params: Unsubscribe paramaters to be loaded on the unsubscribe_method [optional] (dict).
	:param attachments: List of attachments.
	:param reply_to: Reply-To Email Address.
	:param message_id: Used for threading. If a reply is received to this email, Message-Id is sent back as In-Reply-To in received email.
	:param in_reply_to: Used to send the Message-Id of a received email back as In-Reply-To.
	:param send_after: Send after the given datetime.
	:param expose_recipients: Display all recipients in the footer message - "This email was sent to"
	:param communication: Communication link to be set in Email Queue record
	:param inline_images: List of inline images as {"filename", "filecontent"}. All src properties will be replaced with random Content-Id
	:param template: Name of html template from templates/emails folder
	:param args: Arguments for rendering the template
	:param header: Append header in email
	:param with_container: Wraps email inside a styled container
	"""

	if recipients is None:
		recipients = []
	if cc is None:
		cc = []
	if bcc is None:
		bcc = []

	text_content = None
	if template:
		message, text_content = get_email_from_template(template, args)

	message = content or message

	if as_markdown:
		from frappe.utils import md_to_html

		message = md_to_html(message)

	if not delayed:
		now = True

	from frappe.email.doctype.email_queue.email_queue import QueueBuilder

	builder = QueueBuilder(
		recipients=recipients,
		sender=sender,
		subject=subject,
		message=message,
		text_content=text_content,
		reference_doctype=doctype or reference_doctype,
		reference_name=name or reference_name,
		add_unsubscribe_link=add_unsubscribe_link,
		unsubscribe_method=unsubscribe_method,
		unsubscribe_params=unsubscribe_params,
		unsubscribe_message=unsubscribe_message,
		attachments=attachments,
		reply_to=reply_to,
		cc=cc,
		bcc=bcc,
		message_id=message_id,
		in_reply_to=in_reply_to,
		send_after=send_after,
		expose_recipients=expose_recipients,
		send_priority=send_priority,
		queue_separately=queue_separately,
		communication=communication,
		read_receipt=read_receipt,
		is_notification=is_notification,
		inline_images=inline_images,
		header=header,
		print_letterhead=print_letterhead,
		with_container=with_container,
	)

	# build email queue and send the email if send_now is True.
	builder.process(send_now=now)


whitelisted = []
guest_methods = []
xss_safe_methods = []
allowed_http_methods_for_whitelisted_func = {}


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
		global whitelisted, guest_methods, xss_safe_methods, allowed_http_methods_for_whitelisted_func

		# get function from the unbound / bound method
		# this is needed because functions can be compared, but not methods
		method = None
		if hasattr(fn, "__func__"):
			method = fn
			fn = method.__func__

		whitelisted.append(fn)
		allowed_http_methods_for_whitelisted_func[fn] = methods

		if allow_guest:
			guest_methods.append(fn)

			if xss_safe:
				xss_safe_methods.append(fn)

		return method or fn

	return innerfn


def is_whitelisted(method):
	from frappe.utils import sanitize_html

	is_guest = session["user"] == "Guest"
	if method not in whitelisted or is_guest and method not in guest_methods:
		summary = _("You are not permitted to access this resource.")
		detail = _("Function {0} is not whitelisted.").format(
			bold(f"{method.__module__}.{method.__name__}")
		)
		msg = f"<details><summary>{summary}</summary>{detail}</details>"
		throw(msg, PermissionError, title="Method Not Allowed")

	if is_guest and method not in xss_safe_methods:
		# strictly sanitize form_dict
		# escapes html characters like <> except for predefined tags like a, b, ul etc.
		for key, value in form_dict.items():
			if isinstance(value, str):
				form_dict[key] = sanitize_html(value)


def read_only():
	def innfn(fn):
		def wrapper_fn(*args, **kwargs):
			if conf.read_from_replica:
				connect_replica()

			try:
				retval = fn(*args, **get_newargs(fn, kwargs))
			finally:
				if local and hasattr(local, "primary_db"):
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

	if local.flags.in_test or local.session.user == "Administrator":
		return

	if isinstance(roles, str):
		roles = (roles,)

	if not set(roles).intersection(get_roles()):
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
		if local.flags.in_test:
			return _dict()
		else:
			raise


def clear_cache(user: str | None = None, doctype: str | None = None):
	"""Clear **User**, **DocType** or global cache.

	:param user: If user is given, only user cache is cleared.
	:param doctype: If doctype is given, only DocType cache is cleared."""
	import frappe.cache_manager
	import frappe.utils.caching

	if doctype:
		frappe.cache_manager.clear_doctype_cache(doctype)
		reset_metadata_version()
	elif user:
		frappe.cache_manager.clear_user_cache(user)
	else:  # everything
		from frappe import translate

		frappe.cache_manager.clear_user_cache()
		frappe.cache_manager.clear_domain_cache()
		translate.clear_cache()
		reset_metadata_version()
		local.cache = {}
		local.new_doc_templates = {}

		for fn in get_hooks("clear_cache"):
			get_attr(fn)()

	frappe.utils.caching._SITE_CACHE.clear()
	local.role_permissions = {}
	if hasattr(local, "request_cache"):
		local.request_cache.clear()
	if hasattr(local, "system_settings"):
		del local.system_settings
	if hasattr(local, "website_settings"):
		del local.website_settings


def only_has_select_perm(doctype, user=None, ignore_permissions=False):
	if ignore_permissions:
		return False

	if not user:
		user = local.session.user

	import frappe.permissions

	permissions = frappe.permissions.get_role_permissions(doctype, user=user)

	if permissions.get("select") and not permissions.get("read"):
		return True
	else:
		return False


def has_permission(
	doctype=None,
	ptype="read",
	doc=None,
	user=None,
	verbose=False,
	throw=False,
	*,
	parent_doctype=None,
):
	"""
	Returns True if the user has permission `ptype` for given `doctype` or `doc`
	Raises `frappe.PermissionError` if user isn't permitted and `throw` is truthy

	:param doctype: DocType for which permission is to be check.
	:param ptype: Permission type (`read`, `write`, `create`, `submit`, `cancel`, `amend`). Default: `read`.
	:param doc: [optional] Checks User permissions for given doc.
	:param user: [optional] Check for given user. Default: current user.
	:param verbose: DEPRECATED, will be removed in a future release.
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
		raise_exception=throw,
		parent_doctype=parent_doctype,
	)

	if throw and not out:
		# mimics frappe.throw
		document_label = f"{_(doc.doctype)} {doc.name}" if doc else _(doctype)
		msgprint(
			_("No permission for {0}").format(document_label),
			raise_exception=ValidationError,
			title=None,
			indicator="red",
			is_minimizable=None,
			wide=None,
			as_list=False,
		)

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
			doc = get_doc(doctype, doc)

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
	"""Returns True if `istable` property (indicating child Table) is set for given DocType."""

	def get_tables():
		return db.get_values("DocType", filters={"istable": 1}, order_by=None, pluck=True)

	tables = cache().get_value("is_table", get_tables)
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

	if not length:
		length = 56

	return secrets.token_hex(math.ceil(length / 2))[:length]


def reset_metadata_version():
	"""Reset `metadata_version` (Client (Javascript) build ID) hash."""
	v = generate_hash()
	cache().set_value("metadata_version", v)
	return v


def new_doc(
	doctype: str,
	parent_doc: Optional["Document"] = None,
	parentfield: str | None = None,
	as_dict: bool = False,
) -> "Document":
	"""Returns a new document of the given DocType with defaults set.

	:param doctype: DocType of the new document.
	:param parent_doc: [optional] add to parent document.
	:param parentfield: [optional] add against this `parentfield`."""
	from frappe.model.create_new import get_new_doc

	return get_new_doc(doctype, parent_doc, parentfield, as_dict=as_dict)


def set_value(doctype, docname, fieldname, value=None):
	"""Set document value. Calls `frappe.client.set_value`"""
	import frappe.client

	return frappe.client.set_value(doctype, docname, fieldname, value)


def get_cached_doc(*args, **kwargs) -> "Document":
	def _respond(doc, from_redis=False):
		if isinstance(doc, dict):
			local.document_cache[key] = doc = get_doc(doc)

		elif from_redis:
			local.document_cache[key] = doc

		return doc

	if key := can_cache_doc(args):
		# local cache - has "ready" `Document` objects
		if doc := local.document_cache.get(key):
			return _respond(doc)

		# redis cache
		if doc := cache().hget("document_cache", key):
			return _respond(doc, True)

	# Not found in local/redis, fetch from DB
	doc = get_doc(*args, **kwargs)

	# Store in cache
	if not key:
		key = get_document_cache_key(doc.doctype, doc.name)

	_set_document_in_cache(key, doc)

	return doc


def _set_document_in_cache(key: str, doc: "Document") -> None:
	local.document_cache[key] = doc

	# Avoid setting in local.cache since we're already using local.document_cache above
	# Try pickling the doc object as-is first, else fallback to doc.as_dict()
	try:
		cache().hset("document_cache", key, doc, cache_locally=False)
	except Exception:
		cache().hset("document_cache", key, doc.as_dict(), cache_locally=False)


def can_cache_doc(args) -> str | None:
	"""
	Determine if document should be cached based on get_doc params.
	Returns cache key if doc can be cached, None otherwise.
	"""

	if not args:
		return

	doctype = args[0]
	name = doctype if len(args) == 1 or args[1] is None else args[1]

	# Only cache if both doctype and name are strings
	if isinstance(doctype, str) and isinstance(name, str):
		return get_document_cache_key(doctype, name)


def get_document_cache_key(doctype: str, name: str):
	return f"{doctype}::{name}"


def clear_document_cache(doctype, name):
	cache().hdel("last_modified", doctype)
	key = get_document_cache_key(doctype, name)
	if key in local.document_cache:
		del local.document_cache[key]
	cache().hdel("document_cache", key)
	if doctype == "System Settings" and hasattr(local, "system_settings"):
		delattr(local, "system_settings")
	if doctype == "Website Settings" and hasattr(local, "website_settings"):
		delattr(local, "website_settings")


def get_cached_value(
	doctype: str, name: str, fieldname: str = "name", as_dict: bool = False
) -> Any:
	try:
		doc = get_cached_doc(doctype, name)
	except DoesNotExistError:
		clear_last_message()
		return

	if isinstance(fieldname, str):
		if as_dict:
			throw("Cannot make dict for single fieldname")
		return doc.get(fieldname)

	values = [doc.get(f) for f in fieldname]
	if as_dict:
		return _dict(zip(fieldname, values))
	return values


def get_doc(*args, **kwargs) -> "Document":
	"""Return a `frappe.model.document.Document` object of the given type and name.

	:param arg1: DocType name as string **or** document JSON.
	:param arg2: [optional] Document name as string.

	Examples:

	        # insert a new document
	        todo = frappe.get_doc({"doctype":"ToDo", "description": "test"})
	        todo.insert()

	        # open an existing document
	        todo = frappe.get_doc("ToDo", "TD0001")

	"""
	import frappe.model.document

	doc = frappe.model.document.get_doc(*args, **kwargs)

	# Replace cache if stale one exists
	if (key := can_cache_doc(args)) and cache().hexists("document_cache", key):
		_set_document_in_cache(key, doc)

	return doc


def get_last_doc(doctype, filters=None, order_by="creation desc", *, for_update=False):
	"""Get last created document of this type."""
	d = get_all(doctype, filters=filters, limit_page_length=1, order_by=order_by, pluck="name")
	if d:
		return get_doc(doctype, d[0], for_update=for_update)
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


def delete_doc(
	doctype: str | None = None,
	name: str | None = None,
	force: bool = False,
	ignore_doctypes: list[str] | None = None,
	for_reload: bool = False,
	ignore_permissions: bool = False,
	flags: None = None,
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


def delete_doc_if_exists(doctype, name, force=0):
	"""Delete document if exists."""
	delete_doc(doctype, name, force=force, ignore_missing=True)


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
	old: str,
	new: str,
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


def get_module(modulename):
	"""Returns a module object for given Python module name using `importlib.import_module`."""
	return importlib.import_module(modulename)


def scrub(txt: str) -> str:
	"""Returns sluggified string. e.g. `Sales Order` becomes `sales_order`."""
	return cstr(txt).replace(" ", "_").replace("-", "_").lower()


def unscrub(txt: str) -> str:
	"""Returns titlified string. e.g. `sales_order` becomes `Sales Order`."""
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
	return os.path.join(os.path.dirname(get_module(scrub(modulename)).__file__ or ""), *joins)


def get_module_list(app_name):
	"""Get list of modules for given all via `app/modules.txt`."""
	return get_file_items(os.path.join(os.path.dirname(get_module(app_name).__file__), "modules.txt"))


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
def get_installed_apps(sort=False, frappe_last=False, *, _ensure_on_bench=False):
	"""
	Get list of installed apps in current site.

	:param sort: [DEPRECATED] Sort installed apps based on the sequence in sites/apps.txt
	:param frappe_last: [DEPRECATED] Keep frappe last. Do not use this, reverse the app list instead.
	:param ensure_on_bench: Only return apps that are present on bench.
	"""
	from frappe.utils.deprecations import deprecation_warning

	if getattr(flags, "in_install_db", True):
		return []

	if not db:
		connect()

	installed = json.loads(db.get_global("installed_apps") or "[]")

	if sort:
		if not local.all_apps:
			local.all_apps = cache().get_value("all_apps", get_all_apps)

		deprecation_warning("`sort` argument is deprecated and will be removed in v15.")
		installed = [app for app in local.all_apps if app in installed]

	if _ensure_on_bench:
		all_apps = cache().get_value("all_apps", get_all_apps)
		installed = [app for app in installed if app in all_apps]

	if frappe_last:
		deprecation_warning("`frappe_last` argument is deprecated and will be removed in v15.")
		if "frappe" in installed:
			installed.remove("frappe")
		installed.append("frappe")

	return installed


def get_doc_hooks():
	"""Returns hooked methods for given doc. It will expand the dict tuple if required."""
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


@request_cache
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
			return not isinstance(obj, (types.ModuleType, types.FunctionType, type))

		for key, value in inspect.getmembers(app_hooks, predicate=_is_valid_hook):
			if not key.startswith("_"):
				append_hook(hooks, key, value)
	return hooks


def get_hooks(
	hook: str = None, default: Any | None = "_KEEP_DEFAULT_LIST", app_name: str = None
) -> _dict:
	"""Get hooks via `app/hooks.py`

	:param hook: Name of the hook. Will gather all hooks for this name and return as a list.
	:param default: Default if no hook found.
	:param app_name: Filter by app."""

	if app_name:
		hooks = _dict(_load_app_hooks(app_name))
	else:
		if conf.developer_mode:
			hooks = _dict(_load_app_hooks())
		else:
			hooks = _dict(cache().get_value("app_hooks", _load_app_hooks))

	if hook:
		return hooks.get(hook, ([] if default == "_KEEP_DEFAULT_LIST" else default))
	return hooks


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


def setup_module_map():
	"""Rebuild map of all modules (internal)."""
	_cache = cache()

	if conf.db_name:
		local.app_modules = _cache.get_value("app_modules")
		local.module_app = _cache.get_value("module_app")

	if not (local.app_modules and local.module_app):
		local.module_app, local.app_modules = {}, {}
		for app in get_all_apps(with_internal_apps=True):
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


def read_file(path, raise_not_found=False):
	"""Open a file and return its content as Unicode."""
	if isinstance(path, str):
		path = path.encode("utf-8")

	if os.path.exists(path):
		with open(path) as f:
			return as_unicode(f.read())
	elif raise_not_found:
		raise OSError(f"{path} Not Found")
	else:
		return None


def get_attr(method_string: str) -> Any:
	"""Get python method object from its name."""
	app_name = method_string.split(".", 1)[0]
	if (
		not local.flags.in_uninstall
		and not local.flags.in_install
		and app_name not in get_installed_apps()
	):
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


def get_newargs(fn: Callable, kwargs: dict[str, Any]) -> dict[str, Any]:
	"""Remove any kwargs that are not supported by the function.

	Example:
	        >>> def fn(a=1, b=2): pass

	        >>> get_newargs(fn, {"a": 2, "c": 1})
	                {"a": 2}
	"""

	# if function has any **kwargs parameter that capture arbitrary keyword arguments
	# Ref: https://docs.python.org/3/library/inspect.html#inspect.Parameter.kind
	varkw_exist = False

	if hasattr(fn, "fnargs"):
		fnargs = fn.fnargs
	else:
		signature = inspect.signature(fn)
		fnargs = list(signature.parameters)

		for param_name, parameter in signature.parameters.items():
			if parameter.kind == inspect.Parameter.VAR_KEYWORD:
				varkw_exist = True
				fnargs.remove(param_name)
				break

	newargs = {}
	for a in kwargs:
		if (a in fnargs) or varkw_exist:
			newargs[a] = kwargs.get(a)

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


def copy_doc(doc: "Document", ignore_no_copy: bool = True) -> "Document":
	"""No_copy fields also get copied."""
	import copy

	def remove_no_copy_fields(d):
		for df in d.meta.get("fields", {"no_copy": 1}):
			if hasattr(d, df.fieldname):
				d.set(df.fieldname, None)

	fields_to_clear = ["name", "owner", "creation", "modified", "modified_by"]

	if not local.flags.in_test:
		fields_to_clear.append("docstatus")

	if not isinstance(doc, dict):
		d = doc.as_dict()
	else:
		d = doc

	newdoc = get_doc(copy.deepcopy(d))
	newdoc.set("__islocal", 1)
	for fieldname in fields_to_clear + ["amended_from", "amendment_date"]:
		newdoc.set(fieldname, None)

	if not ignore_no_copy:
		remove_no_copy_fields(newdoc)

	for i, d in enumerate(newdoc.get_all_children()):
		d.set("__islocal", 1)

		for fieldname in fields_to_clear:
			d.set(fieldname, None)

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

	cache().set_value(f"message_id:{message_id}", message, expires_in_sec=60)
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
	:param order_by: Order By e.g. `modified desc`.
	:param limit_start: Start results at record #. Default 0.
	:param limit_page_length: No of records in the page. Default 20.

	Example usage:

	        # simple dict filter
	        frappe.get_list("ToDo", fields=["name", "description"], filters = {"owner":"test@example.com"})

	        # filter as a list of lists
	        frappe.get_list("ToDo", fields="*", filters = [["modified", ">", "2014-01-01"]])

	        # filter as a list of dicts
	        frappe.get_list("ToDo", fields="*", filters = {"description": ("like", "test%")})
	"""
	import frappe.model.db_query

	return frappe.model.db_query.DatabaseQuery(doctype).execute(*args, **kwargs)


def get_all(doctype, *args, **kwargs):
	"""List database query via `frappe.model.db_query`. Will **not** check for permissions.
	Parameters are same as `frappe.get_list`

	:param doctype: DocType on which query is to be made.
	:param fields: List of fields or `*`. Default is: `["name"]`.
	:param filters: List of filters (see example).
	:param order_by: Order By e.g. `modified desc`.
	:param limit_start: Start results at record #. Default 0.
	:param limit_page_length: No of records in the page. Default 20.

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


def as_json(obj: dict | list, indent=1, separators=None) -> str:
	from frappe.utils.response import json_handler

	if separators is None:
		separators = (",", ": ")

	try:
		return json.dumps(
			obj, indent=indent, sort_keys=True, default=json_handler, separators=separators
		)
	except TypeError:
		# this would break in case the keys are not all os "str" type - as defined in the JSON
		# adding this to ensure keys are sorted (expected behaviour)
		sorted_obj = dict(sorted(obj.items(), key=lambda kv: str(kv[0])))
		return json.dumps(sorted_obj, indent=indent, default=json_handler, separators=separators)


def are_emails_muted():
	from frappe.utils import cint

	return flags.mute_emails or cint(conf.get("mute_emails") or 0) or False


def get_test_records(doctype):
	"""Returns list of objects from `test_records.json` in the given doctype's folder."""
	from frappe.modules import get_doctype_module, get_module_path

	path = os.path.join(
		get_module_path(get_doctype_module(doctype)), "doctype", scrub(doctype), "test_records.json"
	)
	if os.path.exists(path):
		with open(path) as f:
			return json.loads(f.read())
	else:
		return []


def format_value(*args, **kwargs):
	"""Format value with given field properties.

	:param value: Value to be formatted.
	:param df: (Optional) DocField object with properties `fieldtype`, `options` etc."""
	import frappe.utils.formatters

	return frappe.utils.formatters.format_value(*args, **kwargs)


def format(*args, **kwargs):
	"""Format value with given field properties.

	:param value: Value to be formatted.
	:param df: (Optional) DocField object with properties `fieldtype`, `options` etc."""
	import frappe.utils.formatters

	return frappe.utils.formatters.format_value(*args, **kwargs)


def get_print(
	doctype=None,
	name=None,
	print_format=None,
	style=None,
	html=None,
	as_pdf=False,
	doc=None,
	output=None,
	no_letterhead=0,
	password=None,
	pdf_options=None,
	letterhead=None,
):
	"""Get Print Format for given document.

	:param doctype: DocType of document.
	:param name: Name of document.
	:param print_format: Print Format name. Default 'Standard',
	:param style: Print Format style.
	:param as_pdf: Return as PDF. Default False.
	:param password: Password to encrypt the pdf with. Default None"""
	from frappe.utils.pdf import get_pdf
	from frappe.website.serve import get_response_content

	local.form_dict.doctype = doctype
	local.form_dict.name = name
	local.form_dict.format = print_format
	local.form_dict.style = style
	local.form_dict.doc = doc
	local.form_dict.no_letterhead = no_letterhead
	local.form_dict.letterhead = letterhead

	pdf_options = pdf_options or {}
	if password:
		pdf_options["password"] = password

	if not html:
		html = get_response_content("printview")

	if as_pdf:
		return get_pdf(html, options=pdf_options, output=output)
	else:
		return html


def attach_print(
	doctype,
	name,
	file_name=None,
	print_format=None,
	style=None,
	html=None,
	doc=None,
	lang=None,
	print_letterhead=True,
	password=None,
):
	from frappe.utils import scrub_urls

	if not file_name:
		file_name = name
	file_name = cstr(file_name).replace(" ", "").replace("/", "-")

	print_settings = db.get_singles_dict("Print Settings")

	_lang = local.lang

	# set lang as specified in print format attachment
	if lang:
		local.lang = lang
	local.flags.ignore_print_permissions = True

	no_letterhead = not print_letterhead

	kwargs = dict(
		print_format=print_format,
		style=style,
		html=html,
		doc=doc,
		no_letterhead=no_letterhead,
		password=password,
	)

	content = ""
	if int(print_settings.send_print_as_pdf or 0):
		ext = ".pdf"
		kwargs["as_pdf"] = True
		content = get_print(doctype, name, **kwargs)
	else:
		ext = ".html"
		content = scrub_urls(get_print(doctype, name, **kwargs)).encode("utf-8")

	out = {"fname": file_name + ext, "fcontent": content}

	local.flags.ignore_print_permissions = False
	# reset lang to original local lang
	local.lang = _lang

	return out


def publish_progress(*args, **kwargs):
	"""Show the user progress for a long request

	:param percent: Percent progress
	:param title: Title
	:param doctype: Optional, for document type
	:param docname: Optional, for document name
	:param description: Optional description
	"""
	import frappe.realtime

	return frappe.realtime.publish_progress(*args, **kwargs)


def publish_realtime(*args, **kwargs):
	"""Publish real-time updates

	:param event: Event name, like `task_progress` etc.
	:param message: JSON message object. For async must contain `task_id`
	:param room: Room in which to publish update (default entire site)
	:param user: Transmit to user
	:param doctype: Transmit to doctype, docname
	:param docname: Transmit to doctype, docname
	:param after_commit: (default False) will emit after current transaction is committed
	"""
	import frappe.realtime

	return frappe.realtime.publish_realtime(*args, **kwargs)


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

	elif local.cache[namespace][key] is None and regenerate_if_none:
		# if key exists but the previous result was None
		local.cache[namespace][key] = generator()

	return local.cache[namespace][key]


def enqueue(*args, **kwargs):
	"""
	Enqueue method to be executed using a background worker

	:param method: method string or method object
	:param queue: (optional) should be either long, default or short
	:param timeout: (optional) should be set according to the functions
	:param event: this is passed to enable clearing of jobs from queues
	:param is_async: (optional) if is_async=False, the method is executed immediately, else via a worker
	:param job_name: (optional) can be used to name an enqueue call, which can be used to prevent duplicate calls
	:param kwargs: keyword arguments to be passed to the method
	"""
	import frappe.utils.background_jobs

	return frappe.utils.background_jobs.enqueue(*args, **kwargs)


def task(**task_kwargs):
	def decorator_task(f):
		f.enqueue = lambda **fun_kwargs: enqueue(f, **task_kwargs, **fun_kwargs)
		return f

	return decorator_task


def enqueue_doc(*args, **kwargs):
	"""
	Enqueue method to be executed using a background worker

	:param doctype: DocType of the document on which you want to run the event
	:param name: Name of the document on which you want to run the event
	:param method: method string or method object
	:param queue: (optional) should be either long, default or short
	:param timeout: (optional) should be set according to the functions
	:param kwargs: keyword arguments to be passed to the method
	"""
	import frappe.utils.background_jobs

	return frappe.utils.background_jobs.enqueue_doc(*args, **kwargs)


def get_doctype_app(doctype):
	def _get_doctype_app():
		doctype_module = local.db.get_value("DocType", doctype, "module")
		return local.module_app[scrub(doctype_module)]

	return local_cache("doctype_app", doctype, generator=_get_doctype_app)


loggers = {}
log_level = None


def logger(
	module=None, with_more_info=False, allow_site=True, filter=None, max_size=100_000, file_count=20
):
	"""Returns a python logger that uses StreamHandler"""
	from frappe.utils.logger import get_logger

	return get_logger(
		module=module,
		with_more_info=with_more_info,
		allow_site=allow_site,
		filter=filter,
		max_size=max_size,
		file_count=file_count,
	)


def log_error(title=None, message=None, reference_doctype=None, reference_name=None):
	"""Log error to Error Log"""
	# Parameter ALERT:
	# the title and message may be swapped
	# the better API for this is log_error(title, message), and used in many cases this way
	# this hack tries to be smart about whats a title (single line ;-)) and fixes it

	traceback = None
	if message:
		if "\n" in title:  # traceback sent as title
			traceback, title = title, message
		else:
			traceback = message

	title = title or "Error"
	traceback = as_unicode(traceback or get_traceback(with_context=True))

	error_log = get_doc(
		doctype="Error Log",
		error=traceback,
		method=title,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
	)

	if flags.read_only:
		error_log.deferred_insert()
	else:
		return error_log.insert(ignore_permissions=True)


def get_desk_link(doctype, name):
	html = (
		'<a href="/app/Form/{doctype}/{name}" style="font-weight: bold;">{doctype_local} {name}</a>'
	)
	return html.format(doctype=doctype, name=name, doctype_local=_(doctype))


def bold(text):
	return f"<strong>{text}</strong>"


def safe_eval(code, eval_globals=None, eval_locals=None):
	"""A safer `eval`"""
	whitelisted_globals = {"int": int, "float": float, "long": int, "round": round}
	code = unicodedata.normalize("NFKC", code)

	UNSAFE_ATTRIBUTES = {
		# Generator Attributes
		"gi_frame",
		"gi_code",
		# Coroutine Attributes
		"cr_frame",
		"cr_code",
		"cr_origin",
		# Async Generator Attributes
		"ag_code",
		"ag_frame",
		# Traceback Attributes
		"tb_frame",
		"tb_next",
		# Format Attributes
		"format",
		"format_map",
	}

	for attribute in UNSAFE_ATTRIBUTES:
		if attribute in code:
			throw(f'Illegal rule {bold(code)}. Cannot use "{attribute}"')

	if "__" in code:
		throw(f'Illegal rule {bold(code)}. Cannot use "__"')

	if not eval_globals:
		eval_globals = {}

	eval_globals["__builtins__"] = {}
	eval_globals.update(whitelisted_globals)
	return eval(code, eval_globals, eval_locals)


def get_website_settings(key):
	if not hasattr(local, "website_settings"):
		try:
			local.website_settings = get_cached_doc("Website Settings")
		except DoesNotExistError:
			clear_last_message()
			return

	return local.website_settings.get(key)


def get_system_settings(key):
	if not hasattr(local, "system_settings"):
		try:
			local.system_settings = get_cached_doc("System Settings")
		except DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return local.system_settings.get(key)


def get_active_domains():
	from frappe.core.doctype.domain_settings.domain_settings import get_active_domains

	return get_active_domains()


def get_version(doctype, name, limit=None, head=False, raise_err=True):
	"""
	Returns a list of version information of a given DocType.

	Note: Applicable only if DocType has changes tracked.

	Example
	>>> frappe.get_version('User', 'foobar@gmail.com')
	>>>
	[
	        {
	                "version": [version.data],			# Refer Version DocType get_diff method and data attribute
	                "user": "admin@gmail.com",			# User that created this version
	                "creation": <datetime.datetime>		# Creation timestamp of that object.
	        }
	]
	"""
	meta = get_meta(doctype)
	if meta.track_changes:
		names = get_all(
			"Version",
			filters={
				"ref_doctype": doctype,
				"docname": name,
				"order_by": "creation" if head else None,
				"limit": limit,
			},
			as_list=1,
		)

		from frappe.utils import dictify, safe_json_loads, squashify

		versions = []

		for name in names:
			name = squashify(name)
			doc = get_doc("Version", name)

			data = doc.data
			data = safe_json_loads(data)
			data = dictify(dict(version=data, user=doc.owner, creation=doc.creation))

			versions.append(data)

		return versions
	else:
		if raise_err:
			raise ValueError(_("{0} has no versions tracked.").format(doctype))


@whitelist(allow_guest=True)
def ping():
	return "pong"


def safe_encode(param, encoding="utf-8"):
	try:
		param = param.encode(encoding)
	except Exception:
		pass
	return param


def safe_decode(param, encoding="utf-8"):
	try:
		param = param.decode(encoding)
	except Exception:
		pass
	return param


def parse_json(val):
	from frappe.utils import parse_json

	return parse_json(val)


def mock(type, size=1, locale="en"):
	import faker

	results = []
	fake = faker.Faker(locale)
	if type not in dir(fake):
		raise ValueError("Not a valid mock type.")
	else:
		for i in range(size):
			data = getattr(fake, type)()
			results.append(data)

	from frappe.utils import squashify

	return squashify(results)


def validate_and_sanitize_search_inputs(fn):
	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		from frappe.desk.search import sanitize_searchfield
		from frappe.utils import cint

		kwargs.update(dict(zip(fn.__code__.co_varnames, args)))
		sanitize_searchfield(kwargs["searchfield"])
		kwargs["start"] = cint(kwargs["start"])
		kwargs["page_len"] = cint(kwargs["page_len"])

		if kwargs["doctype"] and not db.exists("DocType", kwargs["doctype"]):
			return []

		return fn(**kwargs)

	return wrapper


if _tune_gc:
	# generational GC gets triggered after certain allocs (g0) which is 700 by default.
	# This number is quite small for frappe where a single query can potentially create 700+
	# objects easily.
	# Bump this number higher, this will make GC less aggressive but that improves performance of
	# everything else.
	g0, g1, g2 = gc.get_threshold()  # defaults are 700, 10, 10.
	gc.set_threshold(g0 * 10, g1 * 2, g2 * 2)
