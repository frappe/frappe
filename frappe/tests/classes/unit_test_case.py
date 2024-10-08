import datetime
import json
import logging
import os
import unittest
from collections.abc import Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytz

import frappe
from frappe.model.base_document import BaseDocument
from frappe.utils import cint
from frappe.utils.data import get_datetime, get_system_timezone

from .context_managers import debug_on

logger = logging.Logger(__file__)

datetime_like_types = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)


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
		cls.module = frappe.get_module(cls.__module__)

	@classmethod
	def _get_doctype_from_module(cls):
		module_path = cls.__module__.split(".")
		try:
			doctype_index = module_path.index("doctype")
			doctype_snake_case = module_path[doctype_index + 1]
			json_file_path = Path(*module_path[:-1]).joinpath(f"{doctype_snake_case}.json")
			if json_file_path.is_file():
				doctype_data = json.loads(json_file_path.read_text())
				return doctype_data.get("name")
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
