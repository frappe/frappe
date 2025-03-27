"""
This module provides functionality for discovering and organizing tests in the Frappe framework.

Key components:
- discover_all_tests: Discovers all tests for specified app(s)
- discover_doctype_tests: Discovers tests for specific DocType(s)
- discover_module_tests: Discovers tests for specific module(s)
- _add_module_tests: Helper function to add tests from a module to the test runner

The module uses various strategies to find and categorize tests, including:
- Walking through app directories
- Importing test modules
- Categorizing tests (e.g., unit, integration)
- Filtering tests based on configuration

It also includes error handling and logging to facilitate debugging and provide informative error messages.

Usage:
These functions are typically called by the test runner to populate the test suite before execution.
"""

import importlib
import logging
import os
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from .utils import debug_timer

if TYPE_CHECKING:
	from .runner import TestRunner

logger = logging.getLogger("frappe.testing.discovery")


@debug_timer
def discover_all_tests(apps: list[str], runner) -> "TestRunner":
	"""Discover all tests for the specified app(s)"""
	logger.debug(f"Discovering tests for apps: {apps}")
	if isinstance(apps, str):
		apps = [apps]
	try:
		for app in apps:
			app_path = Path(frappe.get_app_path(app))
			for path, folders, files in os.walk(app_path):
				folders[:] = [f for f in folders if not f.startswith(".")]
				for dontwalk in ("node_modules", "locals", "public", "__pycache__"):
					if dontwalk in folders:
						folders.remove(dontwalk)
				if os.path.sep.join(["doctype", "doctype", "boilerplate"]) in path:
					continue
				path = Path(path)
				for file in [
					path.joinpath(filename)
					for filename in files
					if filename.startswith("test_")
					and filename.endswith(".py")
					and filename != "test_runner.py"
				]:
					module_name = f"{'.'.join(file.relative_to(app_path.parent).parent.parts)}.{file.stem}"
					_add_module_tests(runner, app, module_name)
	except Exception as e:
		logger.error(f"Error discovering all tests for {apps}: {e!s}")
		raise TestRunnerError(f"Failed to discover tests for {apps}: {e!s}") from e
	return runner


@debug_timer
def discover_doctype_tests(doctypes: list[str], runner, app: str, force: bool = False) -> "TestRunner":
	"""Discover tests for the specified doctype(s)"""
	if isinstance(doctypes, str):
		doctypes = [doctypes]
	_app = app
	for doctype in doctypes:
		try:
			module = frappe.db.get_value("DocType", doctype, "module")
			if not module:
				raise TestRunnerError(f"Invalid doctype {doctype}")

			# Check if the DocType belongs to the specified app
			doctype_app = frappe.db.get_value("Module Def", module, "app_name")
			if app is None:
				_app = doctype_app
			elif doctype_app != app:
				raise TestRunnerError(
					f"Mismatch between specified app '{app}' and doctype app '{doctype_app}'"
				)
			test_module = frappe.modules.utils.get_module_name(doctype, module, "test_")
			force and frappe.db.delete(doctype)
			_add_module_tests(runner, _app, test_module)
		except Exception as e:
			logger.error(f"Error discovering tests for {doctype}: {e!s}")
			raise TestRunnerError(f"Failed to discover tests for {doctype}: {e!s}") from e
	return runner


@debug_timer
def discover_module_tests(modules: list[str], runner, app: str) -> "TestRunner":
	"""Discover tests for the specified test module"""
	if isinstance(modules, str):
		modules = [modules]
	_app = app
	try:
		for module in modules:
			module_app = module.split(".")[0]
			if app is None:
				_app = module_app
			elif app != module_app:
				raise TestRunnerError(f"Mismatch between specified app '{app}' and module app '{module_app}'")
			_add_module_tests(runner, _app, module)
	except Exception as e:
		logger.error(f"Error discovering tests for {module}: {e!s}")
		raise TestRunnerError(f"Failed to discover tests for {module}: {e!s}") from e
	return runner


def _add_module_tests(runner, app: str, module: str):
	module = importlib.import_module(module)
	if runner.cfg.case:
		test_suite = unittest.TestLoader().loadTestsFromTestCase(getattr(module, runner.cfg.case))
	else:
		test_suite = unittest.TestLoader().loadTestsFromModule(module)

	for test in runner._iterate_suite(test_suite):
		if runner.cfg.tests and test._testMethodName not in runner.cfg.tests:
			continue
		match test:
			case IntegrationTestCase():
				category = "integration"
			case UnitTestCase():
				category = "unit"
			case _:
				category = "unspecified-category"
				if any(b.__name__ == "FrappeTestCase" for b in test.__class__.__bases__):
					from frappe.deprecation_dumpster import deprecation_warning

					deprecation_warning(
						"2024-20-08",
						"v17",
						"accurate categorization of FrappeTestCase will be removed from this runner",
					)
					category = "old-frappe-test-class-category"
		if runner.cfg.selected_categories and category not in runner.cfg.selected_categories:
			continue
		runner.per_app_categories[app][category].addTest(test)


class TestRunnerError(Exception):
	"""Custom exception for test runner errors"""
