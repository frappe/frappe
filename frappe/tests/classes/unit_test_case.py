import datetime
import json
import logging
import os
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import frappe
from frappe.model.base_document import BaseDocument
from frappe.utils import cint

logger = logging.Logger(__file__)

datetime_like_types = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)


class BaseTestCase:
	@classmethod
	def registerAs(cls, _as):
		def decorator(cm_func):
			setattr(cls, cm_func.__name__, _as(cm_func))
			return cm_func

		return decorator


class UnitTestCase(unittest.TestCase, BaseTestCase):
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
		if getattr(cls, "_unit_test_case_class_setup_done", None):
			return
		super().setUpClass()
		cls.doctype = _get_doctype_from_module(cls)
		cls.module = frappe.get_module(cls.__module__)
		# Test Environment
		frappe.set_user("Administrator")
		# Test Environment (cleanup)
		cls.addClassCleanup(frappe.set_user, "Administrator")
		cls._unit_test_case_class_setup_done = True

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

	@staticmethod
	def normalize_html(code: str) -> str:
		"""Formats HTML consistently so simple string comparisons can work on them."""
		from bs4 import BeautifulSoup

		return BeautifulSoup(code, "html.parser").prettify(formatter=None)

	@staticmethod
	def normalize_sql(query: str) -> str:
		"""Formats SQL consistently so simple string comparisons can work on them."""
		import sqlparse

		return sqlparse.format(query.strip(), keyword_case="upper", reindent=True, strip_comments=True)


def _get_doctype_from_module(cls):
	namespace = cls.__module__.split(".")
	path = frappe.get_pymodule_path(cls.__module__)
	try:
		doctype_index = namespace.index("doctype")
		doctype_snake_case = namespace[doctype_index + 1]
		# need to check json spec: todo -> ToDo (not Todo); not inferable
		json_file_path = Path(path).joinpath(f"{doctype_snake_case}.json")
		if json_file_path.is_file():
			doctype_data = json.loads(json_file_path.read_text())
			return doctype_data.get("name")
	except (ValueError, IndexError):
		# 'doctype' not found in module_path
		pass
	return None
