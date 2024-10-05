import copy
import datetime
import functools
import os
import pdb
import signal
import sys
import traceback
import unittest
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager, contextmanager
from functools import cache
from importlib import reload
from pathlib import Path
from typing import Any, Union
from unittest.mock import patch

import pytz

import frappe
from frappe.model.base_document import BaseDocument, get_controller
from frappe.model.naming import revert_series_if_last
from frappe.modules import load_doctype_module
from frappe.utils import cint
from frappe.utils.data import convert_utc_to_timezone, get_datetime, get_system_timezone

datetime_like_types = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)
import logging

logger = logging.Logger(__file__)


@cache
def get_modules(doctype):
	"""Get the modules for the specified doctype"""
	module = frappe.db.get_value("DocType", doctype, "module")
	try:
		test_module = load_doctype_module(doctype, module, "test_")
		if test_module:
			reload(test_module)
	except ImportError:
		test_module = None

	return module, test_module


@cache
def get_dependencies(doctype):
	"""Get the dependencies for the specified doctype"""
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


# Test record generation


def make_test_records(doctype, force=False, commit=False):
	return list(_make_test_records(doctype, force, commit))


def make_test_records_for_doctype(doctype, force=False, commit=False):
	return list(_make_test_records_for_doctype(doctype, force, commit))


def make_test_objects(doctype, test_records=None, reset=False, commit=False):
	return list(_make_test_objects(doctype, test_records, reset, commit))


def _make_test_records(doctype, force=False, commit=False):
	"""Make test records for the specified doctype"""

	loadme = False

	if doctype not in frappe.local.test_objects:
		loadme = True
		frappe.local.test_objects[doctype] = []  # infinite recursion guard, here

	# First, create test records for dependencies
	for dependency in get_dependencies(doctype):
		if dependency != "[Select]" and dependency not in frappe.local.test_objects:
			yield from _make_test_records(dependency, force, commit)

	# Then, create test records for the doctype itself
	if loadme:
		# Yield the doctype and record length
		yield (
			doctype,
			len(
				# Create all test records
				list(_make_test_records_for_doctype(doctype, force, commit))
			),
		)


def _make_test_records_for_doctype(doctype, force=False, commit=False):
	"""Make test records for the specified doctype"""

	test_record_log_instance = TestRecordLog()
	if not force and doctype in test_record_log_instance.get():
		return

	module, test_module = get_modules(doctype)
	if hasattr(test_module, "_make_test_records"):
		yield from test_module._make_test_records()
	elif hasattr(test_module, "test_records"):
		yield from _make_test_objects(doctype, test_module.test_records, force, commit=commit)
	else:
		test_records = frappe.get_test_records(doctype)
		if test_records:
			yield from _make_test_objects(doctype, test_records, force, commit=commit)
		elif logger.getEffectiveLevel() < logging.INFO:
			print_mandatory_fields(doctype)

	test_record_log_instance.add(doctype)


def _make_test_objects(doctype, test_records=None, reset=False, commit=False):
	"""Generator function to make test objects"""

	def revert_naming(d):
		if getattr(d, "naming_series", None):
			revert_series_if_last(d.naming_series, d.name)

	if test_records is None:
		test_records = frappe.get_test_records(doctype)

	for doc in test_records:
		if not reset:
			frappe.db.savepoint("creating_test_record")

		if not doc.get("doctype"):
			doc["doctype"] = doctype

		d = frappe.copy_doc(doc)

		if d.meta.get_field("naming_series"):
			if not d.naming_series:
				d.naming_series = "_T-" + d.doctype + "-"

		if doc.get("name"):
			d.name = doc.get("name")
		else:
			d.set_new_name()

		if frappe.db.exists(d.doctype, d.name) and not reset:
			frappe.db.rollback(save_point="creating_test_record")
			# do not create test records, if already exists
			continue

		# submit if docstatus is set to 1 for test record
		docstatus = d.docstatus

		d.docstatus = 0

		try:
			d.run_method("before_test_insert")
			d.insert(ignore_if_duplicate=True)

			if docstatus == 1:
				d.submit()

		except frappe.NameError:
			revert_naming(d)

		except Exception as e:
			if (
				d.flags.ignore_these_exceptions_in_test
				and e.__class__ in d.flags.ignore_these_exceptions_in_test
			):
				revert_naming(d)
			else:
				logger.debug(f"Error in making test record for {d.doctype} {d.name}")
				raise

		if commit:
			frappe.db.commit()

		frappe.local.test_objects[doctype] += d.name
		yield d.name


def print_mandatory_fields(doctype):
	"""Print mandatory fields for the specified doctype"""
	meta = frappe.get_meta(doctype)
	logger.debug(f"Please setup make_test_records for: {doctype}")
	logger.debug("-" * 60)
	logger.debug(f"Autoname: {meta.autoname or ''}")
	logger.debug("Mandatory Fields:")
	for d in meta.get("fields", {"reqd": 1}):
		logger.debug(f" - {d.parent}:{d.fieldname} | {d.fieldtype} | {d.options or ''}")
	logger.debug("")


class TestRecordLog:
	def __init__(self):
		self.log_file = Path(frappe.get_site_path(".test_log"))
		self._log = None

	def get(self):
		if self._log is None:
			self._log = self._read_log()
		return self._log

	def add(self, doctype):
		log = self.get()
		if doctype not in log:
			log.append(doctype)
			self._write_log(log)

	def _read_log(self):
		if self.log_file.exists():
			with self.log_file.open() as f:
				return f.read().splitlines()
		return []

	def _write_log(self, log):
		with self.log_file.open("w") as f:
			f.write("\n".join(l for l in log if l is not None))


def debug_on(*exceptions):
	"""
	A decorator to automatically start the debugger when specified exceptions occur.

	This decorator allows you to automatically invoke the debugger (pdb) when certain
	exceptions are raised in the decorated function. If no exceptions are specified,
	it defaults to catching AssertionError.

	Args:
	        *exceptions: Variable length argument list of exception classes to catch.
	                If none provided, defaults to (AssertionError,).

	Returns:
	        function: A decorator function.

	Usage:
	        1. Basic usage (catches AssertionError):
	                @debug_on()
	                def test_assertion_error():
	                        assert False, "This will start the debugger"

	        2. Catching specific exceptions:
	                @debug_on(ValueError, TypeError)
	                def test_specific_exceptions():
	                        raise ValueError("This will start the debugger")

	        3. Using on a method in a test class:
	                class TestMyFunctionality(unittest.TestCase):
	                        @debug_on(ZeroDivisionError)
	                        def test_division_by_zero(self):
	                                result = 1 / 0

	Note:
	        When an exception is caught, this decorator will print the exception traceback
	        and then start the post-mortem debugger, allowing you to inspect the state of
	        the program at the point where the exception was raised.
	"""
	if not exceptions:
		exceptions = (AssertionError,)

	def decorator(f):
		@functools.wraps(f)
		def wrapper(*args, **kwargs):
			try:
				return f(*args, **kwargs)
			except exceptions as e:
				exc_type, exc_value, exc_traceback = sys.exc_info()
				# Pretty print the exception
				print("\n\033[91m" + "=" * 60 + "\033[0m")  # Red line
				print("\033[93m" + str(exc_type.__name__) + ": " + str(exc_value) + "\033[0m")
				print("\033[91m" + "=" * 60 + "\033[0m")  # Red line

				# Print the formatted traceback
				traceback_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
				for line in traceback_lines:
					print("\033[96m" + line.rstrip() + "\033[0m")  # Cyan color

				print("\033[91m" + "=" * 60 + "\033[0m")  # Red line
				print("\033[92mEntering post-mortem debugging\033[0m")
				print("\033[91m" + "=" * 60 + "\033[0m")  # Red line
				pdb.post_mortem()

				raise e

		return wrapper

	return decorator


class UnitTestCase(unittest.TestCase):
	"""Unit test class for Frappe tests.

	This class extends unittest.TestCase and provides additional utilities
	specific to Frappe framework. It's designed for testing individual
	components or functions in isolation.

	Key features:
	- Custom assertions for Frappe-specific comparisons
	- Utilities for HTML and SQL normalization
	- Context managers for user switching and time freezing

	Note: If you override `setUpClass`, make sure to call `super().setUpClass()`
	to maintain the functionality of this base class.
	"""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.doctype = cls._get_doctype_from_module()

	@classmethod
	def _get_doctype_from_module(cls):
		module_path = cls.__module__.split(".")
		try:
			doctype_index = module_path.index("doctype")
			doctype_snake_case = module_path[doctype_index + 1]
			return frappe.unscrub(doctype_snake_case)
		except (ValueError, IndexError):
			# 'doctype' not found in module_path
			pass
		return None

	def _apply_debug_decorator(self, exceptions=()):
		setattr(self, self._testMethodName, debug_on(*exceptions)(getattr(self, self._testMethodName)))

	def assertQueryEqual(self, first: str, second: str) -> None:
		self.assertEqual(self.normalize_sql(first), self.normalize_sql(second))

	def assertSequenceSubset(self, larger: Sequence, smaller: Sequence, msg: str | None = None) -> None:
		"""Assert that `expected` is a subset of `actual`."""
		self.assertTrue(set(smaller).issubset(set(larger)), msg=msg)

	# --- Frappe Framework specific assertions
	def assertDocumentEqual(self, expected: dict | BaseDocument, actual: BaseDocument) -> None:
		"""Compare a (partial) expected document with actual Document."""

		if isinstance(expected, BaseDocument):
			expected = expected.as_dict()

		for field, value in expected.items():
			if isinstance(value, list):
				actual_child_docs = actual.get(field)
				self.assertEqual(len(value), len(actual_child_docs), msg=f"{field} length should be same")
				for exp_child, actual_child in zip(value, actual_child_docs, strict=False):
					self.assertDocumentEqual(exp_child, actual_child)
			else:
				self._compare_field(value, actual.get(field), actual, field)

	def _compare_field(self, expected: Any, actual: Any, doc: BaseDocument, field: str) -> None:
		msg = f"{field} should be same."

		if isinstance(expected, float):
			precision = doc.precision(field)
			self.assertAlmostEqual(
				expected, actual, places=precision, msg=f"{field} should be same to {precision} digits"
			)
		elif isinstance(expected, bool | int):
			self.assertEqual(expected, cint(actual), msg=msg)
		elif isinstance(expected, datetime_like_types) or isinstance(actual, datetime_like_types):
			self.assertEqual(str(expected), str(actual), msg=msg)
		else:
			self.assertEqual(expected, actual, msg=msg)

	def normalize_html(self, code: str) -> str:
		"""Formats HTML consistently so simple string comparisons can work on them."""
		from bs4 import BeautifulSoup

		return BeautifulSoup(code, "html.parser").prettify(formatter=None)

	@contextmanager
	def set_user(self, user: str) -> AbstractContextManager[None]:
		try:
			old_user = frappe.session.user
			frappe.set_user(user)
			yield
		finally:
			frappe.set_user(old_user)

	def normalize_sql(self, query: str) -> str:
		"""Formats SQL consistently so simple string comparisons can work on them."""
		import sqlparse

		return sqlparse.format(query.strip(), keyword_case="upper", reindent=True, strip_comments=True)

	@classmethod
	def enable_safe_exec(cls) -> None:
		"""Enable safe exec and disable them after test case is completed."""
		from frappe.installer import update_site_config
		from frappe.utils.safe_exec import SAFE_EXEC_CONFIG_KEY

		cls._common_conf = os.path.join(frappe.local.sites_path, "common_site_config.json")
		update_site_config(SAFE_EXEC_CONFIG_KEY, 1, validate=False, site_config_path=cls._common_conf)

		cls.addClassCleanup(
			lambda: update_site_config(
				SAFE_EXEC_CONFIG_KEY, 0, validate=False, site_config_path=cls._common_conf
			)
		)

	@staticmethod
	@contextmanager
	def patch_hooks(overridden_hooks: dict) -> AbstractContextManager[None]:
		get_hooks = frappe.get_hooks

		def patched_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
			if hook in overridden_hooks:
				return overridden_hooks[hook]
			return get_hooks(hook, default, app_name)

		with patch.object(frappe, "get_hooks", patched_hooks):
			yield

	@contextmanager
	def freeze_time(
		self, time_to_freeze: Any, is_utc: bool = False, *args: Any, **kwargs: Any
	) -> AbstractContextManager[None]:
		from freezegun import freeze_time

		if not is_utc:
			# Freeze time expects UTC or tzaware objects. We have neither, so convert to UTC.
			timezone = pytz.timezone(get_system_timezone())
			time_to_freeze = timezone.localize(get_datetime(time_to_freeze)).astimezone(pytz.utc)

		with freeze_time(time_to_freeze, *args, **kwargs):
			yield


class IntegrationTestCase(UnitTestCase):
	"""Integration test class for Frappe tests.

	Key features:
	- Automatic database setup and teardown
	- Utilities for managing database connections
	- Context managers for query counting and Redis call monitoring

	Note: If you override `setUpClass`, make sure to call `super().setUpClass()`
	to maintain the functionality of this base class.
	"""

	TEST_SITE = "test_site"

	SHOW_TRANSACTION_COMMIT_WARNINGS = False
	maxDiff = 10_000  # prints long diffs but useful in CI

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.TEST_SITE = getattr(frappe.local, "site", None) or cls.TEST_SITE
		frappe.init(cls.TEST_SITE)
		cls.ADMIN_PASSWORD = frappe.get_conf(cls.TEST_SITE).admin_password
		cls._primary_connection = frappe.local.db
		cls._secondary_connection = None
		# flush changes done so far to avoid flake
		frappe.db.commit()
		if cls.SHOW_TRANSACTION_COMMIT_WARNINGS:
			frappe.db.before_commit.add(_commit_watcher)

		# enqueue teardown actions (executed in LIFO order)
		cls.addClassCleanup(_restore_thread_locals, copy.deepcopy(frappe.local.flags))
		cls.addClassCleanup(_rollback_db)

	@classmethod
	def tearDownClass(cls) -> None:
		# Add any necessary teardown code here
		super().tearDownClass()

	def setUp(self) -> None:
		super().setUp()
		# Add any per-test setup code here

	def tearDown(self) -> None:
		# Add any per-test teardown code here
		super().tearDown()

	@contextmanager
	def primary_connection(self) -> AbstractContextManager[None]:
		"""Switch to primary DB connection

		This is used for simulating multiple users performing actions by simulating two DB connections"""
		try:
			current_conn = frappe.local.db
			frappe.local.db = self._primary_connection
			yield
		finally:
			frappe.local.db = current_conn

	@contextmanager
	def secondary_connection(self) -> AbstractContextManager[None]:
		"""Switch to secondary DB connection."""
		if self._secondary_connection is None:
			frappe.connect()  # get second connection
			self._secondary_connection = frappe.local.db

		try:
			current_conn = frappe.local.db
			frappe.local.db = self._secondary_connection
			yield
		finally:
			frappe.local.db = current_conn
			self.addCleanup(self._rollback_connections)

	def _rollback_connections(self) -> None:
		self._primary_connection.rollback()
		self._secondary_connection.rollback()

	@contextmanager
	def assertQueryCount(self, count: int) -> AbstractContextManager[None]:
		queries = []

		def _sql_with_count(*args, **kwargs):
			ret = orig_sql(*args, **kwargs)
			queries.append(args[0].last_query)
			return ret

		try:
			orig_sql = frappe.db.__class__.sql
			frappe.db.__class__.sql = _sql_with_count
			yield
			self.assertLessEqual(len(queries), count, msg="Queries executed: \n" + "\n\n".join(queries))
		finally:
			frappe.db.__class__.sql = orig_sql

	@contextmanager
	def assertRedisCallCounts(self, count: int) -> AbstractContextManager[None]:
		commands = []

		def execute_command_and_count(*args, **kwargs):
			ret = orig_execute(*args, **kwargs)
			key_len = 2
			if "H" in args[0]:
				key_len = 3
			commands.append((args)[:key_len])
			return ret

		try:
			orig_execute = frappe.cache.execute_command
			frappe.cache.execute_command = execute_command_and_count
			yield
			self.assertLessEqual(
				len(commands), count, msg="commands executed: \n" + "\n".join(str(c) for c in commands)
			)
		finally:
			frappe.cache.execute_command = orig_execute

	@contextmanager
	def assertRowsRead(self, count: int) -> AbstractContextManager[None]:
		rows_read = 0

		def _sql_with_count(*args, **kwargs):
			nonlocal rows_read

			ret = orig_sql(*args, **kwargs)
			# count of last touched rows as per DB-API 2.0 https://peps.python.org/pep-0249/#rowcount
			rows_read += cint(frappe.db._cursor.rowcount)
			return ret

		try:
			orig_sql = frappe.db.sql
			frappe.db.sql = _sql_with_count
			yield
			self.assertLessEqual(rows_read, count, msg="Queries read more rows than expected")
		finally:
			frappe.db.sql = orig_sql

	@contextmanager
	def switch_site(self, site: str) -> AbstractContextManager[None]:
		"""Switch connection to different site.
		Note: Drops current site connection completely."""

		try:
			old_site = frappe.local.site
			frappe.init(site, force=True)
			frappe.connect()
			yield
		finally:
			frappe.init(old_site, force=True)
			frappe.connect()

	@staticmethod
	@contextmanager
	def change_settings(doctype, settings_dict=None, /, commit=False, **settings):
		"""A context manager to ensure that settings are changed before running
		function and restored after running it regardless of exceptions occurred.
		This is useful in tests where you want to make changes in a function but
		don't retain those changes.
		import and use as decorator to cover full function or using `with` statement.

		example:
		@change_settings("Print Settings", {"send_print_as_pdf": 1})
		def test_case(self):
		        ...

		@change_settings("Print Settings", send_print_as_pdf=1)
		def test_case(self):
		        ...
		"""

		if settings_dict is None:
			settings_dict = settings

		try:
			settings = frappe.get_doc(doctype)
			# remember setting
			previous_settings = copy.deepcopy(settings_dict)
			for key in previous_settings:
				previous_settings[key] = getattr(settings, key)

			# change setting
			for key, value in settings_dict.items():
				setattr(settings, key, value)
			settings.save(ignore_permissions=True)
			# singles are cached by default, clear to avoid flake
			frappe.db.value_cache[settings] = {}
			if commit:
				frappe.db.commit()
			yield  # yield control to calling function

		finally:
			# restore settings
			settings = frappe.get_doc(doctype)
			for key, value in previous_settings.items():
				setattr(settings, key, value)
			settings.save(ignore_permissions=True)
			if commit:
				frappe.db.commit()


# TODO: move to dumpster
FrappeTestCase = IntegrationTestCase
change_settings = IntegrationTestCase.change_settings
patch_hooks = UnitTestCase.patch_hooks


class MockedRequestTestCase(IntegrationTestCase):
	def setUp(self):
		import responses

		self.responses = responses.RequestsMock()
		self.responses.start()

		self.addCleanup(self.responses.stop)
		self.addCleanup(self.responses.reset)

		return super().setUp()


def _commit_watcher():
	import traceback

	print("Warning:, transaction committed during tests.")
	traceback.print_stack(limit=10)


def _rollback_db():
	frappe.db.value_cache = {}
	frappe.db.rollback()


def _restore_thread_locals(flags):
	frappe.local.flags = flags
	frappe.local.error_log = []
	frappe.local.message_log = []
	frappe.local.debug_log = []
	frappe.local.conf = frappe._dict(frappe.get_site_config())
	frappe.local.cache = {}
	frappe.local.lang = "en"
	frappe.local.preload_assets = {"style": [], "script": [], "icons": []}

	if hasattr(frappe.local, "request"):
		delattr(frappe.local, "request")


def timeout(seconds=30, error_message="Test timed out."):
	"""Timeout decorator to ensure a test doesn't run for too long.

	adapted from https://stackoverflow.com/a/2282656"""

	# Support @timeout (without function call)
	no_args = bool(callable(seconds))
	actual_timeout = 30 if no_args else seconds
	actual_error_message = "Test timed out" if no_args else error_message

	def decorator(func):
		def _handle_timeout(signum, frame):
			raise Exception(actual_error_message)

		def wrapper(*args, **kwargs):
			signal.signal(signal.SIGALRM, _handle_timeout)
			signal.alarm(actual_timeout)
			try:
				result = func(*args, **kwargs)
			finally:
				signal.alarm(0)
			return result

		return wrapper

	if no_args:
		return decorator(seconds)

	return decorator


def check_orpahned_doctypes():
	"""Check that all doctypes in DB actually exist after patch test"""

	doctypes = frappe.get_all("DocType", {"custom": 0}, pluck="name")
	orpahned_doctypes = []

	for doctype in doctypes:
		try:
			get_controller(doctype)
		except ImportError:
			orpahned_doctypes.append(doctype)

	if orpahned_doctypes:
		frappe.throw(
			"Following doctypes exist in DB without controller.\n {}".format("\n".join(orpahned_doctypes))
		)
