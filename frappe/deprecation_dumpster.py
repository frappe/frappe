"""
Welcome to the Deprecation Dumpster: Where Old Code Goes to Party! 🎉🗑️

This file is the final resting place (or should we say, "retirement home"?) for all the deprecated functions and methods of the Frappe framework. It's like a code nursing home, but with more monkey-patching and less bingo.

Each function or method that checks in here comes with its own personalized decorator, complete with:
1. The date it was marked for deprecation (its "over the hill" birthday)
2. The Frappe version in which it will be removed (its "graduation" to the great codebase in the sky)
3. A user-facing note on alternative solutions (its "parting wisdom")

Warning: The global namespace herein is more patched up than a sailor's favorite pair of jeans. Proceed with caution and a sense of humor!

Remember, deprecated doesn't mean useless - it just means these functions are enjoying their golden years before their final bow. Treat them with respect, and maybe bring them some virtual prune juice.

Enjoy your stay in the Deprecation Dumpster, where every function gets a second chance to shine (or at least, to not break everything).
"""

import inspect
import os
import sys
import warnings


def colorize(text, color_code):
	if sys.stdout.isatty():
		return f"\033[{color_code}m{text}\033[0m"
	return text


class Color:
	RED = 91
	YELLOW = 93
	CYAN = 96


class FrappeDeprecationWarning(Warning):
	...


try:
	# since python 3.13, PEP 702
	from warnings import deprecated as _deprecated
except ImportError:
	import functools
	import warnings
	from collections.abc import Callable
	from typing import Optional, TypeVar, Union, overload

	T = TypeVar("T", bound=Callable)

	def _deprecated(message: str, category=FrappeDeprecationWarning, stacklevel=1) -> Callable[[T], T]:
		def decorator(func: T) -> T:
			@functools.wraps(func)
			def wrapper(*args, **kwargs):
				if message:
					warning_msg = f"{func.__name__} is deprecated.\n{message}"
				else:
					warning_msg = f"{func.__name__} is deprecated."
				warnings.warn(warning_msg, category=category, stacklevel=stacklevel + 1)
				return func(*args, **kwargs)

			return wrapper
			wrapper.__deprecated__ = True  # hint for the type checker

		return decorator


def deprecated(original: str, marked: str, graduation: str, msg: str, stacklevel: int = 1):
	"""Decorator to wrap a function/method as deprecated.

	Arguments:
	        - original: frappe.utils.make_esc  (fully qualified)
	        - marked: 2024-09-13  (the date it has been marked)
	        - graduation: v17  (generally: current version + 2)
	"""

	def decorator(func):
		# Get the filename of the caller
		frame = inspect.currentframe()
		caller_filepath = frame.f_back.f_code.co_filename
		if os.path.basename(caller_filepath) != "deprecation_dumpster.py":
			raise RuntimeError(
				colorize("The deprecated function ", Color.YELLOW)
				+ colorize(func.__name__, Color.CYAN)
				+ colorize(" can only be called from ", Color.YELLOW)
				+ colorize("frappe/deprecation_dumpster.py\n", Color.CYAN)
				+ colorize("Move the entire function there and import it back via adding\n ", Color.YELLOW)
				+ colorize(f"from frappe.deprecation_dumpster import {func.__name__}\n", Color.CYAN)
				+ colorize("to file\n ", Color.YELLOW)
				+ colorize(caller_filepath, Color.CYAN)
			)

		func.__name__ = original
		wrapper = _deprecated(
			colorize(f"It was marked on {marked} for removal from {graduation} with note: ", Color.RED)
			+ colorize(f"{msg}", Color.YELLOW),
			stacklevel=stacklevel,
		)

		return functools.update_wrapper(wrapper, func)(func)

	return decorator


def deprecation_warning(marked: str, graduation: str, msg: str):
	"""Warn in-place from a deprecated code path, for objects use `@deprecated` decorator from the deprectation_dumpster"

	Arguments:
	        - marked: 2024-09-13  (the date it has been marked)
	        - graduation: v17  (generally: current version + 2)
	"""

	warnings.warn(
		colorize(
			f"This codepath was marked (DATE: {marked}) deprecated"
			f" for removal (from {graduation} onwards); note:\n ",
			Color.RED,
		)
		+ colorize(f"{msg}\n", Color.YELLOW),
		category=DeprecationWarning,
		stacklevel=2,
	)


### Party starts here


@deprecated(
	"frappe.init (old calling signature)",
	"2024-09-13",
	"v17",
	"Use the new calling signature: frappe.init(bench: frappe.bench.Bench, force: bool = False) 🎉🗑️",
	stacklevel=3,  # get past functools.dispatch
)
def old_init(site, sites_path, new_site, force) -> None:
	from pathlib import Path

	from frappe import _init
	from frappe.bench import Bench

	implied_bench_path = Path(sites_path).resolve().parent
	bench = Bench(implied_bench_path)
	bench.scope(site)

	return _init(bench.sites.site, force)


def _old_deprecated(func):
	return deprecated(
		"frappe.deprecations.deprecated",
		"2024-09-13",
		"v17",
		"Make use of the frappe/deprecation_dumpster.py file, instead. 🎉🗑️",
	)(_deprecated("")(func))


def _old_deprecation_warning(msg):
	@deprecated(
		"frappe.deprecations.deprecation_warning",
		"2024-09-13",
		"v17",
		"Use frappe.deprecation_dumpster.deprecation_warning, instead. 🎉🗑️",
	)
	def deprecation_warning(message, category=DeprecationWarning, stacklevel=1):
		warnings.warn(message=message, category=category, stacklevel=stacklevel + 2)

	return deprecation_warning(msg)


@deprecated("frappe.utils.make_esc", "unknown", "v17", "Not used anymore.")
def make_esc(esc_chars):
	"""
	Function generator for Escaping special characters
	"""
	return lambda s: "".join("\\" + c if c in esc_chars else c for c in s)


@deprecated(
	"frappe.db.is_column_missing",
	"unknown",
	"v17",
	"Renamed to frappe.db.is_missing_column.",
)
def is_column_missing(e):
	import frappe

	return frappe.db.is_missing_column(e)


@deprecated(
	"frappe.desk.doctype.bulk_update.bulk_update",
	"unknown",
	"v17",
	"Unknown.",
)
def show_progress(docnames, message, i, description):
	import frappe

	n = len(docnames)
	frappe.publish_progress(float(i) * 100 / n, title=message, description=description)


@deprecated(
	"frappe.client.get_js",
	"unknown",
	"v17",
	"Unknown.",
)
def get_js(items):
	"""Load JS code files.  Will also append translations
	and extend `frappe._messages`

	:param items: JSON list of paths of the js files to be loaded."""
	import json

	import frappe
	from frappe import _

	items = json.loads(items)
	out = []
	for src in items:
		src = src.strip("/").split("/")

		if ".." in src or src[0] != "assets":
			frappe.throw(_("Invalid file path: {0}").format("/".join(src)))

		contentpath = os.path.join(frappe.local.sites_path, *src)
		with open(contentpath) as srcfile:
			code = frappe.utils.cstr(srcfile.read())

		out.append(code)

	return out


@deprecated(
	"frappe.utils.print_format.read_multi_pdf",
	"unknown",
	"v17",
	"Unknown.",
)
def read_multi_pdf(output) -> bytes:
	from io import BytesIO

	with BytesIO() as merged_pdf:
		output.write(merged_pdf)
		return merged_pdf.getvalue()


@deprecated("frappe.gzip_compress", "unknown", "v17", "Use py3 methods directly (this was compat for py2).")
def gzip_compress(data, compresslevel=9):
	"""Compress data in one shot and return the compressed string.
	Optional argument is the compression level, in range of 0-9.
	"""
	import io
	from gzip import GzipFile

	buf = io.BytesIO()
	with GzipFile(fileobj=buf, mode="wb", compresslevel=compresslevel) as f:
		f.write(data)
	return buf.getvalue()


@deprecated("frappe.gzip_decompress", "unknown", "v17", "Use py3 methods directly (this was compat for py2).")
def gzip_decompress(data):
	"""Decompress a gzip compressed string in one shot.
	Return the decompressed string.
	"""
	import io
	from gzip import GzipFile

	with GzipFile(fileobj=io.BytesIO(data)) as f:
		return f.read()


@deprecated(
	"frappe.email.doctype.email_queue.email_queue.send_mail",
	"unknown",
	"v17",
	"Unknown.",
)
def send_mail(email_queue_name, smtp_server_instance=None):
	"""This is equivalent to EmailQueue.send.

	This provides a way to make sending mail as a background job.
	"""
	from frappe.email.doctype.email_queue.email_queue import EmailQueue

	record = EmailQueue.find(email_queue_name)
	record.send(smtp_server_instance=smtp_server_instance)


@deprecated(
	"frappe.geo.country_info.get_translated_dict",
	"unknown",
	"v17",
	"Use frappe.geo.country_info.get_translated_countries, instead.",
)
def get_translated_dict():
	from frappe.geo.country_info import get_translated_countries

	return get_translated_countries()


@deprecated(
	"User.validate_roles",
	"unknown",
	"v17",
	"Use User.populate_role_profile_roles, instead.",
)
def validate_roles(self):
	self.populate_role_profile_roles()


@deprecated("frappe.tests_runner.get_modules", "2024-20-08", "v17", "use frappe.tests.utils.get_modules")
def test_runner_get_modules(doctype):
	from frappe.tests.utils import get_modules

	return get_modules(doctype)


@deprecated(
	"frappe.tests_runner.make_test_records", "2024-20-08", "v17", "use frappe.tests.utils.make_test_records"
)
def test_runner_make_test_records(*args, **kwargs):
	from frappe.tests.utils import make_test_records

	return make_test_records(*args, **kwargs)


@deprecated(
	"frappe.tests_runner.make_test_objects", "2024-20-08", "v17", "use frappe.tests.utils.make_test_objects"
)
def test_runner_make_test_objects(*args, **kwargs):
	from frappe.tests.utils import make_test_objects

	return make_test_objects(*args, **kwargs)


@deprecated(
	"frappe.tests_runner.make_test_records_for_doctype",
	"2024-20-08",
	"v17",
	"use frappe.tests.utils.make_test_records_for_doctype",
)
def test_runner_make_test_records_for_doctype(*args, **kwargs):
	from frappe.tests.utils import make_test_records_for_doctype

	return make_test_records_for_doctype(*args, **kwargs)


@deprecated(
	"frappe.tests_runner.print_mandatory_fields",
	"2024-20-08",
	"v17",
	"no public api anymore",
)
def test_runner_print_mandatory_fields(*args, **kwargs):
	from frappe.tests.utils.generators import print_mandatory_fields

	return print_mandatory_fields(*args, **kwargs)


@deprecated(
	"frappe.tests_runner.get_test_record_log",
	"2024-20-08",
	"v17",
	"no public api anymore",
)
def test_runner_get_test_record_log(doctype):
	from frappe.tests.utils.generators import TestRecordManager

	return TestRecordManager().get(doctype)


@deprecated(
	"frappe.tests_runner.add_to_test_record_log",
	"2024-20-08",
	"v17",
	"no public api anymore",
)
def test_runner_add_to_test_record_log(doctype):
	from frappe.tests.utils.generators import TestRecordManager

	return TestRecordManager().add(doctype)


@deprecated(
	"frappe.tests_runner.main",
	"2024-20-08",
	"v17",
	"no public api anymore",
)
def test_runner_main(*args, **kwargs):
	from frappe.commands.testing import main

	return main(*args, **kwargs)


@deprecated(
	"frappe.tests_runner.xmlrunner_wrapper",
	"2024-20-08",
	"v17",
	"no public api anymore",
)
def test_xmlrunner_wrapper(output):
	"""Convenience wrapper to keep method signature unchanged for XMLTestRunner and TextTestRunner"""
	try:
		import xmlrunner
	except ImportError:
		print("Development dependencies are required to execute this command. To install run:")
		print("$ bench setup requirements --dev")
		raise

	def _runner(*args, **kwargs):
		kwargs["output"] = output
		return xmlrunner.XMLTestRunner(*args, **kwargs)

	return _runner


@deprecated(
	"frappe.tests.upate_system_settings",
	"2024-20-08",
	"v17",
	"use with `self.change_settings(...):` context manager",
)
def tests_update_system_settings(args, commit=False):
	import frappe

	doc = frappe.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
	if commit:
		# moved here
		frappe.db.commit()  # nosemgrep


@deprecated(
	"frappe.tests.get_system_setting",
	"2024-20-08",
	"v17",
	"use `frappe.db.get_single_value('System Settings', key)`",
)
def tests_get_system_setting(key):
	import frappe

	return frappe.db.get_single_value("System Settings", key)


@deprecated(
	"frappe.tests.utils.change_settings",
	"2024-20-08",
	"v17",
	"use `frappe.tests.change_settings` or the cls.change_settings",
)
def tests_change_settings(*args, **kwargs):
	from frappe.tests.classes.context_managers import change_settings

	return change_settings(*args, **kwargs)


@deprecated(
	"frappe.tests.utils.patch_hooks",
	"2024-20-08",
	"v17",
	"use `frappe.tests.patch_hooks` or the cls.patch_hooks",
)
def tests_patch_hooks(*args, **kwargs):
	from frappe.tests.classes.context_managers import patch_hooks

	return patch_hooks(*args, **kwargs)


@deprecated(
	"frappe.tests.utils.debug_on",
	"2024-20-08",
	"v17",
	"use `frappe.tests.debug_on` or the cls.debug_on",
)
def tests_debug_on(*args, **kwargs):
	from frappe.tests.classes.context_managers import debug_on

	return debug_on(*args, **kwargs)


@deprecated(
	"frappe.tests.utils.timeout",
	"2024-20-08",
	"v17",
	"use `frappe.tests.timeout` or the cls.timeout",
)
def tests_timeout(*args, **kwargs):
	from frappe.tests.classes.context_managers import timeout

	return timeout(*args, **kwargs)


def get_tests_FrappeTestCase():
	class CompatFrappeTestCase:
		def __new__(cls, *args, **kwargs):
			from frappe.tests import IntegrationTestCase

			class _CompatFrappeTestCase(IntegrationTestCase):
				def __init__(self, *args, **kwargs):
					deprecation_warning(
						"2024-20-08",
						"v17",
						"Import `frappe.tests.UnitTestCase` or `frappe.tests.IntegrationTestCase` respectively instead of `frappe.tests.utils.FrappeTestCase`",
					)
					super().__init__(*args, **kwargs)

			return _CompatFrappeTestCase(*args, **kwargs)

	return CompatFrappeTestCase


def get_tests_IntegrationTestCase():
	class CompatIntegrationTestCase:
		def __new__(cls, *args, **kwargs):
			from frappe.tests import IntegrationTestCase

			class _CompatIntegrationTestCase(IntegrationTestCase):
				def __init__(self, *args, **kwargs):
					deprecation_warning(
						"2024-20-08",
						"v17",
						"Import `frappe.tests.IntegrationTestCase` instead of `frappe.tests.utils.IntegrationTestCase`",
					)
					super().__init__(*args, **kwargs)

			return _CompatIntegrationTestCase(*args, **kwargs)

	return CompatIntegrationTestCase


def get_tests_UnitTestCase():
	class CompatUnitTestCase:
		def __new__(cls, *args, **kwargs):
			from frappe.tests import UnitTestCase

			class _CompatUnitTestCase(UnitTestCase):
				def __init__(self, *args, **kwargs):
					deprecation_warning(
						"2024-20-08",
						"v17",
						"Import `frappe.tests.UnitTestCase` instead of `frappe.tests.utils.UnitTestCase`",
					)
					super().__init__(*args, **kwargs)

			return _CompatUnitTestCase(*args, **kwargs)

	return CompatUnitTestCase


@deprecated(
	"frappe.model.trace.traced_field_context",
	"2024-20-08",
	"v17",
	"use `cls.trace_fields`",
)
def model_trace_traced_field_context(*args, **kwargs):
	from frappe.tests.classes.context_managers import trace_fields

	return trace_fields(*args, **kwargs)


@deprecated(
	"frappe.tests.utils.get_dependencies",
	"2024-20-09",
	"v17",
	"refactor to use frappe.tests.utils.get_missing_records_doctypes",
)
def tests_utils_get_dependencies(doctype):
	"""Get the dependencies for the specified doctype"""
	import frappe
	from frappe.tests.utils.generators import get_modules

	module, test_module = get_modules(doctype)
	meta = frappe.get_meta(doctype)
	link_fields = meta.get_link_fields()

	for df in meta.get_table_fields():
		link_fields.extend(frappe.get_meta(df.options).get_link_fields())

	options_list = [df.options for df in link_fields]

	if hasattr(test_module, "test_dependencies"):
		options_list += test_module.test_dependencies

	options_list = list(set(options_list))

	if hasattr(test_module, "test_ignore"):
		for doctype_name in test_module.test_ignore:
			if doctype_name in options_list:
				options_list.remove(doctype_name)

	options_list.sort()

	return options_list


@deprecated(
	"frappe.tests_runner.get_dependencies",
	"2024-20-08",
	"v17",
	"refactor to use frappe.tests.utils.get_missing_record_doctypes",
)
def test_runner_get_dependencies(doctype):
	return tests_utils_get_dependencies(doctype)


@deprecated(
	"frappe.get_test_records",
	"2024-20-09",
	"v17",
	"""Please access the global test records pool via cls.globalTestRecords['Some Doc'] -> list.
If not an IntegrationTestCase, use frappe.tests.utils.load_test_records_for (check return type).
""",
)
def frappe_get_test_records(doctype):
	import frappe
	from frappe.tests.utils.generators import load_test_records_for

	frappe.flags.deprecation_dumpster_invoked = True

	records = load_test_records_for(doctype)
	if isinstance(records, dict):
		_records = []
		for doctype, docs in records.items():
			for doc in docs:
				_doc = doc.copy()
				_doc["doctype"] = doctype
				_records.append(_doc)
		return _records
	return records


def get_site_config(sites_path: str | None = None, site_path: str | None = None) -> dict[str, Any]:
	"""Return `site_config.json` combined with `sites/common_site_config.json`.
	`site_config` is a set of site wide settings like database name, password, email etc."""
	config = _dict()

	sites_path = sites_path or getattr(local, "sites_path", None)
	site_path = site_path or getattr(local, "site_path", None)

	common_config = get_common_site_config(sites_path)

	if sites_path:
		config.update(common_config)

	if site_path:
		site_config = os.path.join(site_path, "site_config.json")
		if os.path.exists(site_config):
			try:
				config.update(get_file_json(site_config))
			except Exception as error:
				click.secho(f"{local.site}/site_config.json is invalid", fg="red")
				print(error)
		elif local.site and not local.flags.new_site:
			error_msg = f"{local.site} does not exist."
			if common_config.developer_mode:
				from frappe.utils import get_sites

				all_sites = get_sites()
				error_msg += "\n\nSites on this bench:\n"
				error_msg += "\n".join(f"* {site}" for site in all_sites)

			raise IncorrectSitePath(error_msg)

	# Generalized env variable overrides and defaults
	def db_default_ports(db_type):
		if db_type == "mariadb":
			from frappe.database.mariadb.database import MariaDBDatabase

			return MariaDBDatabase.default_port
		elif db_type == "postgres":
			from frappe.database.postgres.database import PostgresDatabase

			return PostgresDatabase.default_port

		raise ValueError(f"Unsupported db_type={db_type}")

	config["redis_queue"] = (
		os.environ.get("FRAPPE_REDIS_QUEUE") or config.get("redis_queue") or "redis://127.0.0.1:11311"
	)
	config["redis_cache"] = (
		os.environ.get("FRAPPE_REDIS_CACHE") or config.get("redis_cache") or "redis://127.0.0.1:13311"
	)
	config["db_type"] = os.environ.get("FRAPPE_DB_TYPE") or config.get("db_type") or "mariadb"
	config["db_socket"] = os.environ.get("FRAPPE_DB_SOCKET") or config.get("db_socket")
	config["db_host"] = os.environ.get("FRAPPE_DB_HOST") or config.get("db_host") or "127.0.0.1"
	config["db_port"] = int(
		os.environ.get("FRAPPE_DB_PORT") or config.get("db_port") or db_default_ports(config["db_type"])
	)

	# Set the user as database name if not set in config
	config["db_user"] = os.environ.get("FRAPPE_DB_USER") or config.get("db_user") or config.get("db_name")

	# vice versa for dbname if not defined
	config["db_name"] = os.environ.get("FRAPPE_DB_NAME") or config.get("db_name") or config["db_user"]

	# read password
	config["db_password"] = os.environ.get("FRAPPE_DB_PASSWORD") or config.get("db_password")

	# Allow externally extending the config with hooks
	if extra_config := config.get("extra_config"):
		if isinstance(extra_config, str):
			extra_config = [extra_config]
		for hook in extra_config:
			try:
				module, method = hook.rsplit(".", 1)
				config |= getattr(importlib.import_module(module), method)()
			except Exception:
				print(f"Config hook {hook} failed")
				traceback.print_exc()

	return config


def get_common_site_config(sites_path: str | None = None) -> dict[str, Any]:
	"""Return common site config as dictionary.

	This is useful for:
	- checking configuration which should only be allowed in common site config
	- When no site context is present and fallback is required.
	"""
	sites_path = sites_path or getattr(local, "sites_path", None)

	common_site_config = os.path.join(sites_path, "common_site_config.json")
	if os.path.exists(common_site_config):
		try:
			return _dict(get_file_json(common_site_config))
		except Exception as error:
			click.secho("common_site_config.json is invalid", fg="red")
			print(error)
	return _dict()


def get_conf(site: str | None = None) -> dict[str, Any]:
	if hasattr(local, "conf"):
		return local.conf

	# if no site, get from common_site_config.json
	with init_site(site):
		return local.conf


class init_site:
	def __init__(self, site=None):
		"""If site is None, initialize it for empty site ('') to load common_site_config.json"""
		self.site = site

	def __enter__(self):
		init(self.site)
		return local

	def __exit__(self, type, value, traceback):
		destroy()


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


# frappe.utils
def get_path(*path, **kwargs):
	base = kwargs.get("base")
	if not base:
		base = frappe.local.site_path
	return os.path.join(base, *path)


def get_site_base_path():
	return frappe.local.site_path


def get_site_path(*path):
	return get_path(*path, base=get_site_base_path())


def get_bench_path():
	return os.environ.get("FRAPPE_BENCH_ROOT") or os.path.realpath(
		os.path.join(os.path.dirname(frappe.__file__), "..", "..", "..")
	)


def get_bench_id():
	return frappe.get_conf().get("bench_id", get_bench_path().strip("/").replace("/", "-"))


def get_site_id(site=None):
	return f"{site or frappe.local.site}@{get_bench_id()}"


def get_files_path(*path, **kwargs):
	return get_site_path("private" if kwargs.get("is_private") else "public", "files", *path)


def get_backups_path():
	return get_site_path("private", "backups")


def get_sites(sites_path=None):
	if not sites_path:
		sites_path = getattr(frappe.local, "sites_path", None) or "."

	sites = []
	for site in os.listdir(sites_path):
		path = os.path.join(sites_path, site)

		if (
			os.path.isdir(path)
			and not os.path.islink(path)
			and os.path.exists(os.path.join(path, "site_config.json"))
		):
			# is a dir and has site_config.json
			sites.append(site)

	return sorted(sites)


# frappe.installer
def make_conf(
	db_name=None,
	db_password=None,
	site_config=None,
	db_type=None,
	db_socket=None,
	db_host=None,
	db_port=None,
	db_user=None,
):
	site = frappe.site
	make_site_config(
		db_name,
		db_password,
		site_config,
		db_type=db_type,
		db_socket=db_socket,
		db_host=db_host,
		db_port=db_port,
		db_user=db_user,
	)
	frappe.destroy()
	frappe.init(site)


def make_site_config(
	db_name=None,
	db_password=None,
	site_config=None,
	db_type=None,
	db_socket=None,
	db_host=None,
	db_port=None,
	db_user=None,
):
	frappe.create_folder(os.path.join(frappe.local.site_path))
	site_file = get_site_config_path()

	if not os.path.exists(site_file):
		if not (site_config and isinstance(site_config, dict)):
			site_config = get_conf_params(db_name, db_password)

			if db_type:
				site_config["db_type"] = db_type

			if db_socket:
				site_config["db_socket"] = db_socket

			if db_host:
				site_config["db_host"] = db_host

			if db_port:
				site_config["db_port"] = db_port

			site_config["db_user"] = db_user or db_name

		with open(site_file, "w") as f:
			f.write(json.dumps(site_config, indent=1, sort_keys=True))


def update_site_config(key, value, validate=True, site_config_path=None):
	"""Update a value in site_config"""
	from frappe.utils.synchronization import filelock

	if not site_config_path:
		site_config_path = get_site_config_path()

	# Sometimes global config file is passed directly to this function
	_is_global_conf = "common_site_config" in site_config_path

	with filelock("site_config", is_global=_is_global_conf):
		_update_config_file(key=key, value=value, config_file=site_config_path)


def _update_config_file(key: str, value, config_file: str):
	"""Updates site or common config"""
	with open(config_file) as f:
		site_config = json.loads(f.read())

	# In case of non-int value
	if value in ("0", "1"):
		value = int(value)

	# boolean
	if value == "false":
		value = False
	if value == "true":
		value = True

	# remove key if value is None
	if value == "None":
		if key in site_config:
			del site_config[key]
	else:
		site_config[key] = value

	with open(config_file, "w") as f:
		f.write(json.dumps(site_config, indent=1, sort_keys=True))

	if hasattr(frappe.local, "conf"):
		frappe.local.conf[key] = value


def get_site_config_path():
	return os.path.join(frappe.local.site_path, "site_config.json")


def make_site_dirs():
	for dir_path in [
		os.path.join("public", "files"),
		os.path.join("private", "backups"),
		os.path.join("private", "files"),
		"locks",
		"logs",
	]:
		path = frappe.get_site_path(dir_path)
		os.makedirs(path, exist_ok=True)
