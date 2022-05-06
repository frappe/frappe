import copy
import signal
import unittest
from contextlib import contextmanager

import frappe


class FrappeTestCase(unittest.TestCase):
	"""Base test class for Frappe tests."""

	@classmethod
	def setUpClass(cls) -> None:
		frappe.db.commit()
		return super().setUpClass()

	@classmethod
	def tearDownClass(cls) -> None:
		frappe.db.rollback()
		return super().tearDownClass()


@contextmanager
def change_settings(doctype, settings_dict):
	"""A context manager to ensure that settings are changed before running
	function and restored after running it regardless of exceptions occured.
	This is useful in tests where you want to make changes in a function but
	don't retain those changes.
	import and use as decorator to cover full function or using `with` statement.

	example:
	@change_settings("Print Settings", {"send_print_as_pdf": 1})
	def test_case(self):
	        ...
	"""

	try:
		settings = frappe.get_doc(doctype)
		# remember setting
		previous_settings = copy.deepcopy(settings_dict)
		for key in previous_settings:
			previous_settings[key] = getattr(settings, key)

		# change setting
		for key, value in settings_dict.items():
			setattr(settings, key, value)
		settings.save()
		# singles are cached by default, clear to avoid flake
		frappe.db.value_cache[settings] = {}
		yield  # yield control to calling function

	finally:
		# restore settings
		settings = frappe.get_doc(doctype)
		for key, value in previous_settings.items():
			setattr(settings, key, value)
		settings.save()
		frappe.db.value_cache[settings] = {}


def timeout(seconds=30, error_message="Test timed out."):
	"""Timeout decorator to ensure a test doesn't run for too long.

	adapted from https://stackoverflow.com/a/2282656"""

	def decorator(func):
		def _handle_timeout(signum, frame):
			raise Exception(error_message)

		def wrapper(*args, **kwargs):
			signal.signal(signal.SIGALRM, _handle_timeout)
			signal.alarm(seconds)
			try:
				result = func(*args, **kwargs)
			finally:
				signal.alarm(0)
			return result

		return wrapper

	return decorator
