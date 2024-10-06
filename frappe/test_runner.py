# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
This module provides functionality for running tests in Frappe applications.

It includes utilities for running tests for specific doctypes, modules, or entire applications,
as well as functions for creating and managing test records.
"""

from __future__ import annotations

import cProfile
import importlib
import json
import logging
import os
import pstats
import sys
import time
import unittest
from dataclasses import dataclass, field
from functools import wraps
from io import StringIO
from pathlib import Path
from typing import Optional, Union

import click

import frappe
import frappe.utils.scheduler
from frappe.modules import get_module_name
from frappe.tests.utils import IntegrationTestCase
from frappe.utils import cint

SLOW_TEST_THRESHOLD = 2

logger = logging.getLogger(__name__)


def debug_timer(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		start_time = time.monotonic()
		result = func(*args, **kwargs)
		end_time = time.monotonic()
		logger.debug(f" {func.__name__:<50}  ⌛{end_time - start_time:>6.3f} seconds")
		return result

	return wrapper


class TestRunner(unittest.TextTestRunner):
	def __init__(
		self,
		stream=None,
		descriptions=True,
		verbosity=1,
		failfast=False,
		buffer=False,
		resultclass=None,
		warnings=None,
		*,
		tb_locals=False,
		junit_xml_output: bool = False,
		profile: bool = False,
	):
		super().__init__(
			stream=stream,
			descriptions=descriptions,
			verbosity=verbosity,
			failfast=failfast,
			buffer=buffer,
			resultclass=resultclass or TestResult,
			warnings=warnings,
			tb_locals=tb_locals,
		)
		self.junit_xml_output = junit_xml_output
		self.profile = profile
		logger.debug("TestRunner initialized")

	def run(
		self, test_suites: tuple[unittest.TestSuite, unittest.TestSuite]
	) -> tuple[unittest.TestResult, unittest.TestResult | None]:
		unit_suite, integration_suite = test_suites

		if self.profile:
			pr = cProfile.Profile()
			pr.enable()

		# Run unit tests
		click.echo(
			"\n" + click.style(f"Running {unit_suite.countTestCases()} unit tests", fg="cyan", bold=True)
		)
		unit_result = super().run(unit_suite)

		# Run integration tests only if unit tests pass
		integration_result = None
		if unit_result.wasSuccessful():
			click.echo(
				"\n"
				+ click.style(
					f"Running {integration_suite.countTestCases()} integration tests",
					fg="cyan",
					bold=True,
				)
			)
			integration_result = super().run(integration_suite)

		if self.profile:
			pr.disable()
			s = StringIO()
			ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
			ps.print_stats()
			print(s.getvalue())

		return unit_result, integration_result

	def discover_tests(
		self, apps: list[str], config: TestConfig
	) -> tuple[unittest.TestSuite, unittest.TestSuite]:
		logger.debug(f"Discovering tests for apps: {apps}")
		unit_test_suite = unittest.TestSuite()
		integration_test_suite = unittest.TestSuite()

		for app in apps:
			app_path = Path(frappe.get_app_path(app))
			for path, folders, files in os.walk(app_path):
				folders[:] = [f for f in folders if not f.startswith(".")]
				for dontwalk in ("node_modules", "locals", "public", "__pycache__"):
					if dontwalk in folders:
						folders.remove(dontwalk)
				if os.path.sep.join(["doctype", "doctype", "boilerplate"]) in path:
					# in /doctype/doctype/boilerplate/
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
					module = importlib.import_module(module_name)
					self._add_module_tests(module, unit_test_suite, integration_test_suite, config)

		logger.debug(
			f"Discovered {unit_test_suite.countTestCases()} unit tests and {integration_test_suite.countTestCases()} integration tests"
		)
		return unit_test_suite, integration_test_suite

	def discover_doctype_tests(
		self, doctypes: str | list[str], config: TestConfig, force: bool = False
	) -> tuple[unittest.TestSuite, unittest.TestSuite]:
		unit_test_suite = unittest.TestSuite()
		integration_test_suite = unittest.TestSuite()

		if isinstance(doctypes, str):
			doctypes = [doctypes]

		for doctype in doctypes:
			module = frappe.db.get_value("DocType", doctype, "module")
			if not module:
				raise TestRunnerError(f"Invalid doctype {doctype}")

			test_module = get_module_name(doctype, module, "test_")
			if force:
				frappe.db.delete(doctype)

			try:
				module = importlib.import_module(test_module)
				self._add_module_tests(module, unit_test_suite, integration_test_suite, config)
			except ImportError:
				logger.warning(f"No test module found for doctype {doctype}")

		return unit_test_suite, integration_test_suite

	def discover_module_tests(
		self, modules, config: TestConfig
	) -> tuple[unittest.TestSuite, unittest.TestSuite]:
		unit_test_suite = unittest.TestSuite()
		integration_test_suite = unittest.TestSuite()

		modules = [modules] if not isinstance(modules, list | tuple) else modules

		for module in modules:
			module = importlib.import_module(module)
			self._add_module_tests(module, unit_test_suite, integration_test_suite, config)

		return unit_test_suite, integration_test_suite

	def _add_module_tests(
		self,
		module,
		unit_test_suite: unittest.TestSuite,
		integration_test_suite: unittest.TestSuite,
		config: TestConfig,
	):
		if config.case:
			test_suite = unittest.TestLoader().loadTestsFromTestCase(getattr(module, config.case))
		else:
			test_suite = unittest.TestLoader().loadTestsFromModule(module)

		for test in self._iterate_suite(test_suite):
			if config.tests and test._testMethodName not in config.tests:
				continue

			category = "integration" if isinstance(test, IntegrationTestCase) else "unit"

			if config.selected_categories and category not in config.selected_categories:
				continue

			config.categories[category].append(test)
			if category == "unit":
				unit_test_suite.addTest(test)
			else:
				integration_test_suite.addTest(test)

	@staticmethod
	def _iterate_suite(suite):
		for test in suite:
			if isinstance(test, unittest.TestSuite):
				yield from TestRunner._iterate_suite(test)
			elif isinstance(test, unittest.TestCase):
				yield test


class TestResult(unittest.TextTestResult):
	def startTest(self, test):
		self.tb_locals = True
		self._started_at = time.monotonic()
		super(unittest.TextTestResult, self).startTest(test)
		test_class = unittest.util.strclass(test.__class__)
		if getattr(self, "current_test_class", None) != test_class:
			if new_doctypes := getattr(test.__class__, "_newly_created_test_records", None):
				click.echo(f"\n{unittest.util.strclass(test.__class__)}")
				click.secho(
					f"  Test Records created: {', '.join([f'{name} ({qty})' for name, qty in reversed(new_doctypes)])}",
					fg="bright_black",
				)
			else:
				click.echo(f"\n{unittest.util.strclass(test.__class__)}")
			self.current_test_class = test_class

	def getTestMethodName(self, test):
		return test._testMethodName if hasattr(test, "_testMethodName") else str(test)

	def addSuccess(self, test):
		super(unittest.TextTestResult, self).addSuccess(test)
		elapsed = time.monotonic() - self._started_at
		threshold_passed = elapsed >= SLOW_TEST_THRESHOLD
		elapsed_over_threashold = click.style(f" ({elapsed:.03}s)", fg="red") if threshold_passed else ""
		logger.info(
			f"  {click.style(' ✔ ', fg='green')} {self.getTestMethodName(test)}{elapsed_over_threashold}"
		)
		logger.debug(f"=== success === {test} {elapsed}")

	def addError(self, test, err):
		super(unittest.TextTestResult, self).addError(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")
		logger.debug(f"=== error === {test}")

	def addFailure(self, test, err):
		super(unittest.TextTestResult, self).addFailure(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")
		logger.debug(f"=== failure === {test}")

	def addSkip(self, test, reason):
		super(unittest.TextTestResult, self).addSkip(test, reason)
		click.echo(f"  {click.style(' = ', fg='white')} {self.getTestMethodName(test)}")
		logger.debug(f"=== skipped === {test}")

	def addExpectedFailure(self, test, err):
		super(unittest.TextTestResult, self).addExpectedFailure(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")
		logger.debug(f"=== expected failure === {test}")

	def addUnexpectedSuccess(self, test):
		super(unittest.TextTestResult, self).addUnexpectedSuccess(test)
		click.echo(f"  {click.style(' ✔ ', fg='green')} {self.getTestMethodName(test)}")
		logger.debug(f"=== unexpected success === {test}")

	def printErrors(self):
		click.echo("\n")
		self.printErrorList(" ERROR ", self.errors, "red")
		self.printErrorList(" FAIL ", self.failures, "red")

	def printErrorList(self, flavour, errors, color):
		for test, err in errors:
			click.echo(self.separator1)
			click.echo(f"{click.style(flavour, bg=color)} {self.getDescription(test)}")
			click.echo(self.separator2)
			click.echo(err)

	def __str__(self):
		return f"Tests: {self.testsRun}, Failing: {len(self.failures)}, Errors: {len(self.errors)}"


class TestRunnerError(Exception):
	"""Custom exception for test runner errors"""

	pass


logging.basicConfig(format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
	"""Configuration class for test runner"""

	profile: bool = False
	failfast: bool = False
	junit_xml_output: bool = False
	tests: tuple = ()
	case: str | None = None
	pdb_on_exceptions: tuple | None = None
	categories: dict = field(default_factory=lambda: {"unit": [], "integration": []})
	selected_categories: list[str] = field(default_factory=list)
	skip_before_tests: bool = False


def xmlrunner_wrapper(output):
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


def main(
	site: str | None = None,
	app: str | None = None,
	module: str | None = None,
	doctype: str | None = None,
	module_def: str | None = None,
	verbose: bool = False,
	tests: tuple = (),
	force: bool = False,
	profile: bool = False,
	junit_xml_output: str | None = None,
	doctype_list_path: str | None = None,
	failfast: bool = False,
	case: str | None = None,
	skip_before_tests: bool = False,
	pdb_on_exceptions: bool = False,
	selected_categories: list[str] | None = None,
) -> None:
	"""Main function to run tests"""
	logger.setLevel(logging.DEBUG if verbose else logging.INFO)
	start_time = time.time()

	# Check for mutually exclusive arguments
	exclusive_args = [doctype, doctype_list_path, module_def, module]
	if sum(arg is not None for arg in exclusive_args) > 1:
		error_message = (
			"Error: The following arguments are mutually exclusive: "
			"doctype, doctype_list_path, module_def, and module. "
			"Please specify only one of these."
		)
		logger.error(error_message)
		sys.exit(1)

	# Prepare debug log message
	debug_params = []
	for param_name in ["site", "app", "module", "doctype", "module_def", "doctype_list_path"]:
		param_value = locals()[param_name]
		if param_value is not None:
			debug_params.append(f"{param_name}={param_value}")

	if debug_params:
		logger.debug(f"Starting test run with parameters: {', '.join(debug_params)}")
	else:
		logger.debug("Starting test run with no specific parameters")

	test_config = TestConfig(
		profile=profile,
		failfast=failfast,
		junit_xml_output=bool(junit_xml_output),
		tests=tests,
		case=case,
		pdb_on_exceptions=pdb_on_exceptions,
		selected_categories=selected_categories or [],
		skip_before_tests=skip_before_tests,
	)

	_initialize_test_environment(site, test_config)

	xml_output_file = _setup_xml_output(junit_xml_output)

	try:
		# Create TestRunner instance
		runner = TestRunner(
			resultclass=TestResult if not test_config.junit_xml_output else None,
			verbosity=2 if logger.getEffectiveLevel() < logging.INFO else 1,
			failfast=test_config.failfast,
			tb_locals=logger.getEffectiveLevel() <= logging.INFO,
			junit_xml_output=test_config.junit_xml_output,
			profile=test_config.profile,
		)

		if doctype or doctype_list_path:
			doctype = _load_doctype_list(doctype_list_path) if doctype_list_path else doctype
			unit_result, integration_result = _run_doctype_tests(doctype, test_config, runner, force, app)
		elif module_def:
			unit_result, integration_result = _run_module_def_tests(
				app, module_def, test_config, runner, force
			)
		elif module:
			unit_result, integration_result = _run_module_tests(module, test_config, runner, app)
		else:
			unit_result, integration_result = _run_all_tests(app, test_config, runner)

		print_test_results(unit_result, integration_result)

		# Determine overall success
		success = unit_result.wasSuccessful() and (
			integration_result is None or integration_result.wasSuccessful()
		)

		if not success:
			sys.exit(1)

		return unit_result, integration_result

	finally:
		if xml_output_file:
			xml_output_file.close()

		end_time = time.time()
		logger.debug(f"Total test run time: {end_time - start_time:.3f} seconds")


def print_test_results(unit_result: unittest.TestResult, integration_result: unittest.TestResult | None):
	"""Print detailed test results including failures and errors"""
	click.echo("\n" + click.style("Test Results:", fg="cyan", bold=True))

	def _print_result(result, category):
		tests_run = result.testsRun
		failures = len(result.failures)
		errors = len(result.errors)
		click.echo(
			f"\n{click.style(f'{category} Tests:', bold=True)}\n"
			f"  Ran: {click.style(f'{tests_run:<3}', fg='cyan')}"
			f"  Failures: {click.style(f'{failures:<3}', fg='red' if failures else 'green')}"
			f"  Errors: {click.style(f'{errors:<3}', fg='red' if errors else 'green')}"
		)

		if failures > 0:
			click.echo(f"\n{click.style(category + ' Test Failures:', fg='red', bold=True)}")
			for i, failure in enumerate(result.failures, 1):
				click.echo(f"  {i}. {click.style(str(failure[0]), fg='yellow')}")

		if errors > 0:
			click.echo(f"\n{click.style(category + ' Test Errors:', fg='red', bold=True)}")
			for i, error in enumerate(result.errors, 1):
				click.echo(f"  {i}. {click.style(str(error[0]), fg='yellow')}")
				click.echo(click.style("     " + str(error[1]).split("\n")[-2], fg="red"))

	_print_result(unit_result, "Unit")

	if integration_result:
		_print_result(integration_result, "Integration")

	# Print overall status
	total_failures = len(unit_result.failures) + (
		len(integration_result.failures) if integration_result else 0
	)
	total_errors = len(unit_result.errors) + (len(integration_result.errors) if integration_result else 0)

	if total_failures == 0 and total_errors == 0:
		click.echo(f"\n{click.style('All tests passed successfully!', fg='green', bold=True)}")
	else:
		click.echo(f"\n{click.style('Some tests failed or encountered errors.', fg='red', bold=True)}")


@debug_timer
def _initialize_test_environment(site, config: TestConfig):
	"""Initialize the test environment"""
	logger.debug(f"Initializing test environment for site: {site}")
	frappe.init(site)
	if not frappe.db:
		frappe.connect()
	try:
		# require db access
		_disable_scheduler_if_needed()
		frappe.clear_cache()
	except Exception as e:
		logger.error(f"Error connecting to the database: {e!s}")
		raise TestRunnerError(f"Failed to connect to the database: {e}") from e

	# Set various test-related flags
	frappe.flags.in_test = True
	frappe.flags.print_messages = logger.getEffectiveLevel() < logging.INFO
	frappe.flags.tests_verbose = logger.getEffectiveLevel() < logging.INFO
	logger.debug("Test environment initialized")


def _setup_xml_output(junit_xml_output):
	"""Setup XML output for test results if specified"""
	global unittest_runner

	if junit_xml_output:
		xml_output_file = open(junit_xml_output, "wb")
		unittest_runner = xmlrunner_wrapper(xml_output_file)
		return xml_output_file
	else:
		unittest_runner = unittest.TextTestRunner
		return None


def _load_doctype_list(doctype_list_path):
	"""Load the list of doctypes from the specified file"""
	app, path = doctype_list_path.split(os.path.sep, 1)
	with open(frappe.get_app_path(app, path)) as f:
		return f.read().strip().splitlines()


def _run_module_def_tests(
	app, module_def, config: TestConfig, runner: TestRunner, force
) -> tuple[unittest.TestResult, unittest.TestResult | None]:
	"""Run tests for the specified module definition"""
	doctypes = _get_doctypes_for_module_def(app, module_def)
	return _run_doctype_tests(doctypes, config, runner, force, app)


def _get_doctypes_for_module_def(app, module_def):
	"""Get the list of doctypes for the specified module definition"""
	doctypes = []
	doctypes_ = frappe.get_list(
		"DocType",
		filters={"module": module_def, "istable": 0},
		fields=["name", "module"],
		as_list=True,
	)
	for doctype, module in doctypes_:
		test_module = get_module_name(doctype, module, "test_", app=app)
		try:
			importlib.import_module(test_module)
			doctypes.append(doctype)
		except Exception:
			pass
	return doctypes


# Global variable to track scheduler state
scheduler_disabled_by_user = False


def _disable_scheduler_if_needed():
	"""Disable scheduler if it's not already disabled"""
	global scheduler_disabled_by_user
	scheduler_disabled_by_user = frappe.utils.scheduler.is_scheduler_disabled(verbose=False)
	if not scheduler_disabled_by_user:
		frappe.utils.scheduler.disable_scheduler()


def _cleanup_after_tests():
	"""Perform cleanup operations after running tests"""
	global scheduler_disabled_by_user
	if not scheduler_disabled_by_user:
		frappe.utils.scheduler.enable_scheduler()

	if frappe.db:
		frappe.db.commit()
		frappe.clear_cache()


@debug_timer
def _run_all_tests(
	app: str | None, config: TestConfig, runner: TestRunner
) -> tuple[unittest.TestResult, unittest.TestResult | None]:
	"""Run all tests for the specified app or all installed apps"""

	apps = [app] if app else frappe.get_installed_apps()
	logger.debug(f"Running tests for apps: {apps}")
	try:
		unit_test_suite, integration_test_suite = runner.discover_tests(apps, config)
		if config.pdb_on_exceptions:
			for test_suite in (unit_test_suite, integration_test_suite):
				for test_case in runner._iterate_suite(test_suite):
					if hasattr(test_case, "_apply_debug_decorator"):
						test_case._apply_debug_decorator(config.pdb_on_exceptions)

		for app in apps:
			_prepare_integration_tests(runner, integration_test_suite, config, app)
		res = runner.run((unit_test_suite, integration_test_suite))
		_cleanup_after_tests()
		return res
	except Exception as e:
		logger.error(f"Error running all tests for {app or 'all apps'}: {e!s}")
		raise TestRunnerError(f"Failed to run tests for {app or 'all apps'}: {e!s}") from e


@debug_timer
def _run_doctype_tests(
	doctypes, config: TestConfig, runner: TestRunner, force=False, app: str | None = None
) -> tuple[unittest.TestResult, unittest.TestResult | None]:
	"""Run tests for the specified doctype(s)"""

	try:
		unit_test_suite, integration_test_suite = runner.discover_doctype_tests(doctypes, config, force)

		if config.pdb_on_exceptions:
			for test_suite in (unit_test_suite, integration_test_suite):
				for test_case in runner._iterate_suite(test_suite):
					if hasattr(test_case, "_apply_debug_decorator"):
						test_case._apply_debug_decorator(config.pdb_on_exceptions)
		_prepare_integration_tests(runner, integration_test_suite, config, app)
		res = runner.run((unit_test_suite, integration_test_suite))
		_cleanup_after_tests()
		return res
	except Exception as e:
		logger.error(f"Error running tests for doctypes {doctypes}: {e!s}")
		raise TestRunnerError(f"Failed to run tests for doctypes: {e!s}") from e


@debug_timer
def _run_module_tests(
	module, config: TestConfig, runner: TestRunner, app: str | None = None
) -> tuple[unittest.TestResult, unittest.TestResult | None]:
	"""Run tests for the specified module"""
	try:
		unit_test_suite, integration_test_suite = runner.discover_module_tests(module, config)

		if config.pdb_on_exceptions:
			for test_suite in (unit_test_suite, integration_test_suite):
				for test_case in runner._iterate_suite(test_suite):
					if hasattr(test_case, "_apply_debug_decorator"):
						test_case._apply_debug_decorator(config.pdb_on_exceptions)

		_prepare_integration_tests(runner, integration_test_suite, config, app)
		res = runner.run((unit_test_suite, integration_test_suite))
		_cleanup_after_tests()
		return res
	except Exception as e:
		logger.error(f"Error running tests for module {module}: {e!s}")
		raise TestRunnerError(f"Failed to run tests for module: {e!s}") from e


def _prepare_integration_tests(
	runner: TestRunner, integration_test_suite: unittest.TestSuite, config: TestConfig, app: str
) -> None:
	"""Prepare the environment for integration tests."""
	if next(runner._iterate_suite(integration_test_suite), None) is not None:
		# Explanatory comment
		"""
		We perform specific setup steps only for integration tests:

		1. Before Tests Hooks:
		   - Executed only for integration tests unless explicitly skipped.
		   - Provides necessary environment setup for integration tests.
		   - Skipped for unit tests to maintain their independence and isolation.

		2. Global Test Record Creation:
		   - Performed only for integration tests.
		   - Creates or modifies global per-app database records needed for integration tests.
		   - Skipped for unit tests to maintain their isolation and reproducibility.
		"""
		if not config.skip_before_tests:
			_run_before_test_hooks(config, app)
		else:
			logger.debug("Skipping before_tests hooks: Explicitly skipped")
		if app:
			_run_global_test_records_dependencies_install(app)
	else:
		logger.debug("Skipping before_tests hooks and global test record creation: No integration tests")


@debug_timer
def _run_before_test_hooks(config: TestConfig, app: str | None):
	"""Run 'before_tests' hooks"""
	logger.debug(f'Running "before_tests" hooks for {app}')
	for hook_function in frappe.get_hooks("before_tests", app_name=app):
		frappe.get_attr(hook_function)()


@debug_timer
def _run_global_test_records_dependencies_install(app: str):
	"""Run global test records dependencies install"""
	test_module = frappe.get_module(f"{app}.tests")
	logger.debug(f"Loading global tests records from {test_module.__name__}")
	if hasattr(test_module, "global_test_dependencies"):
		for doctype in test_module.global_test_dependencies:
			logger.debug(f" Loading records for {doctype}")
			make_test_records(doctype, commit=True)


# Backwards-compatible aliases
from frappe.tests.utils import (
	TestRecordLog,
	get_dependencies,
	get_modules,
	make_test_objects,
	make_test_records,
	make_test_records_for_doctype,
	print_mandatory_fields,
)


# Compatibility functions
def add_to_test_record_log(doctype):
	TestRecordLog().add(doctype)


def get_test_record_log():
	return TestRecordLog().get()
