import copy
import datetime
import os
import signal
import unittest
from collections.abc import Sequence
from contextlib import contextmanager
from unittest.mock import patch

import pytz

import frappe
from frappe.model.base_document import BaseDocument, get_controller
from frappe.utils import cint
from frappe.utils.data import convert_utc_to_timezone, get_datetime, get_system_timezone

datetime_like_types = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)


class FrappeTestCase(unittest.TestCase):
	"""Base test class for Frappe tests.


	If you specify `setUpClass` then make sure to call `super().setUpClass`
	otherwise this class will become ineffective.
	"""

	TEST_SITE = "test_site"

	SHOW_TRANSACTION_COMMIT_WARNINGS = False
	maxDiff = 10_000  # prints long diffs but useful in CI

	@classmethod
	def setUpClass(cls) -> None:
		cls.TEST_SITE = getattr(frappe.local, "site", None) or cls.TEST_SITE
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

		return super().setUpClass()

	def assertSequenceSubset(self, larger: Sequence, smaller: Sequence, msg=None):
		"""Assert that `expected` is a subset of `actual`."""
		self.assertTrue(set(smaller).issubset(set(larger)), msg=msg)

	# --- Frappe Framework specific assertions
	def assertDocumentEqual(self, expected, actual):
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

	def _compare_field(self, expected, actual, doc: BaseDocument, field: str):
		msg = f"{field} should be same."

		if isinstance(expected, float):
			precision = doc.precision(field)
			self.assertAlmostEqual(
				expected, actual, places=precision, msg=f"{field} should be same to {precision} digits"
			)
		elif isinstance(expected, bool | int):
			self.assertEqual(expected, cint(actual), msg=msg)
		elif isinstance(expected, datetime_like_types):
			self.assertEqual(str(expected), str(actual), msg=msg)
		else:
			self.assertEqual(expected, actual, msg=msg)

	def normalize_html(self, code: str) -> str:
		"""Formats HTML consistently so simple string comparisons can work on them."""
		from bs4 import BeautifulSoup

		return BeautifulSoup(code, "html.parser").prettify(formatter=None)

	def normalize_sql(self, query: str) -> str:
		"""Formats SQL consistently so simple string comparisons can work on them."""
		import sqlparse

		return sqlparse.format(query.strip(), keyword_case="upper", reindent=True, strip_comments=True)

	@contextmanager
	def primary_connection(self):
		"""Switch to primary DB connection

		This is used for simulating multiple users performing actions by simulating two DB connections"""
		try:
			current_conn = frappe.local.db
			frappe.local.db = self._primary_connection
			yield
		finally:
			frappe.local.db = current_conn

	@contextmanager
	def secondary_connection(self):
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

	def _rollback_connections(self):
		self._primary_connection.rollback()
		self._secondary_connection.rollback()

	def assertQueryEqual(self, first: str, second: str):
		self.assertEqual(self.normalize_sql(first), self.normalize_sql(second))

	@contextmanager
	def assertQueryCount(self, count):
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
	def assertRedisCallCounts(self, count):
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
	def assertRowsRead(self, count):
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

	@contextmanager
	def set_user(self, user: str):
		try:
			old_user = frappe.session.user
			frappe.set_user(user)
			yield
		finally:
			frappe.set_user(old_user)

	@contextmanager
	def switch_site(self, site: str):
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

	@contextmanager
	def freeze_time(self, time_to_freeze, *args, **kwargs):
		from freezegun import freeze_time

		# Freeze time expects UTC or tzaware objects. We have neither, so convert to UTC.
		timezone = pytz.timezone(get_system_timezone())
		fake_time_with_tz = timezone.localize(get_datetime(time_to_freeze)).astimezone(pytz.utc)

		with freeze_time(fake_time_with_tz, *args, **kwargs):
			yield


class MockedRequestTestCase(FrappeTestCase):
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


@contextmanager
def change_settings(doctype, settings_dict=None, /, commit=False, **settings):
	"""A context manager to ensure that settings are changed before running
	function and restored after running it regardless of exceptions occured.
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


@contextmanager
def patch_hooks(overridden_hoooks):
	get_hooks = frappe.get_hooks

	def patched_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if hook in overridden_hoooks:
			return overridden_hoooks[hook]
		return get_hooks(hook, default, app_name)

	with patch.object(frappe, "get_hooks", patched_hooks):
		yield


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
