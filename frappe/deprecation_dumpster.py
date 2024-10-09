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
	from frappe.tests.utils.generators import TestRecordLog

	return TestRecordLog().get(doctype)


@deprecated(
	"frappe.tests_runner.add_to_test_record_log",
	"2024-20-08",
	"v17",
	"no public api anymore",
)
def test_runner_add_to_test_record_log(doctype):
	from frappe.tests.utils.generators import TestRecordLog

	return TestRecordLog().add(doctype)


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


@deprecated(
	"frappe.tests.utils.FrappeTestCase",
	"2024-20-08",
	"v17",
	"use `frappe.tests.UnitTestCase` or `frappe.tests.IntegrationTestCase` respectively",
)
def tests_FrappeTestCase(*args, **kwargs):
	from frappe.tests import IntegrationTestCase

	return IntegrationTestCase(*args, **kwargs)


@deprecated(
	"frappe.tests.utils.IntegrationTestCase",
	"2024-20-08",
	"v17",
	"use `frappe.tests.IntegrationTestCase`",
)
def tests_IntegrationTestCase(*args, **kwargs):
	from frappe.tests import IntegrationTestCase

	return IntegrationTestCase(*args, **kwargs)


@deprecated(
	"frappe.tests.utils.UnitTestCase",
	"2024-20-08",
	"v17",
	"use `frappe.tests.UnitTestCase`",
)
def tests_UnitTestCase(*args, **kwargs):
	from frappe.tests import UnitTestCase

	return UnitTestCase(*args, **kwargs)


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
