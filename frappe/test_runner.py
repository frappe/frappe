# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
This module provides functionality for running tests in Frappe applications.

It includes utilities for running tests for specific doctypes, modules, or entire applications,
as well as functions for creating and managing test records.
"""

from __future__ import annotations

import contextlib
import cProfile
import importlib
import json
import logging
import os
import pstats
import sys
import time
import unittest
from collections import defaultdict
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

# Define category priorities
CATEGORY_PRIORITIES = {
	"unit": 1,
	"integration": 2,
	"functional": 3,
	# Add more categories and their priorities as needed
}


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


def iterOnFirstArg(func):
	return lambda self, arg, *args, **kwargs: [
		func(self, a, *args, **kwargs) for a in ([arg] if isinstance(arg, str) else arg)
	][-1]


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
		cfg: TestConfig,
	):
		super().__init__(
			stream=stream,
			descriptions=descriptions,
			verbosity=verbosity,
			failfast=cfg.failfast,
			buffer=buffer,
			resultclass=resultclass or (TestResult if not cfg.junit_xml_output else None),
			warnings=warnings,
			tb_locals=tb_locals,
		)
		self.cfg = cfg
		self.per_app_categories = defaultdict(lambda: defaultdict(unittest.TestSuite))
		logger.debug("TestRunner initialized")

	def run(self, app: str) -> list[unittest.TestResult]:
		results = []
		app_categories = self.per_app_categories.get(app, {})
		sorted_categories = sorted(
			app_categories.items(), key=lambda x: CATEGORY_PRIORITIES.get(x[0], float("inf"))
		)
		for category, suite in sorted_categories:
			if not self._has_tests(suite):
				continue

			self._prepare_category(category, suite, app)
			self._apply_debug_decorators(suite)

			with self._profile():
				click.secho(
					f"\nRunning {suite.countTestCases()} {category} tests for {app}", fg="cyan", bold=True
				)
				result = super().run(suite)
				results.append((category, result))
			if not result.wasSuccessful() and self.cfg.failfast:
				break
		return results

	def _has_tests(self, suite):
		return next(self._iterate_suite(suite), None) is not None

	def _prepare_category(self, category, suite, app):
		dispatcher = {
			"integration": self._prepare_integration,
			# Add other categories here as needed
		}
		prepare_method = dispatcher.get(category.lower())
		if prepare_method:
			prepare_method(suite, app)
		else:
			logger.warning(f"Unknown test category: {category}. No specific preparation performed.")

	def _apply_debug_decorators(self, suite):
		if self.cfg.pdb_on_exceptions:
			for test in self._iterate_suite(suite):
				if hasattr(test, "_apply_debug_decorator"):
					test._apply_debug_decorator(self.cfg.pdb_on_exceptions)

	@contextlib.contextmanager
	def _profile(self):
		if self.cfg.profile:
			pr = cProfile.Profile()
			pr.enable()
		yield
		if self.cfg.profile:
			pr.disable()
			s = StringIO()
			ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
			ps.print_stats()
			print(s.getvalue())

	@iterOnFirstArg
	def discover_tests(self, app: str) -> TestRunner:
		logger.debug(f"Discovering tests for app: {app}")
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
				if filename.startswith("test_") and filename.endswith(".py") and filename != "test_runner.py"
			]:
				module_name = f"{'.'.join(file.relative_to(app_path.parent).parent.parts)}.{file.stem}"
				self._add_module_tests(app, module_name)
		return self

	@iterOnFirstArg
	def discover_doctype_tests(self, doctype: str, app: str | None, force: bool = False) -> TestRunner:
		module = frappe.db.get_value("DocType", doctype, "module")
		if not module:
			raise TestRunnerError(f"Invalid doctype {doctype}")

		# Check if the DocType belongs to the specified app
		doctype_app = frappe.db.get_value("Module Def", module, "app_name")
		if app and doctype_app != app:
			raise TestRunnerError(f"DocType {doctype} does not belong to app {app}")
		elif not app:
			app = doctype_app

		test_module = get_module_name(doctype, module, "test_")
		force and frappe.db.delete(doctype)
		try:
			self._add_module_tests(app, test_module)
		except ImportError:
			logger.warning(f"No test module found for doctype {doctype}")
		return self

	@iterOnFirstArg
	def discover_module_tests(
		self,
		module: str,
		app: str | None,
	) -> TestRunner:
		module_app = frappe.db.get_value("Module Def", module, "app_name")
		if app and module_app != app:
			raise TestRunnerError(f"Module {module} does not belong to app {app}")
		elif not app:
			app = module_app
		self._add_module_tests(app, module)
		return self

	def _add_module_tests(self, app: str, module: str):
		module = importlib.import_module(module)
		if self.cfg.case:
			test_suite = unittest.TestLoader().loadTestsFromTestCase(getattr(module, self.cfg.case))
		else:
			test_suite = unittest.TestLoader().loadTestsFromModule(module)

		for test in self._iterate_suite(test_suite):
			if self.cfg.tests and test._testMethodName not in self.cfg.tests:
				continue
			category = "integration" if isinstance(test, IntegrationTestCase) else "unit"
			if self.cfg.selected_categories and category not in self.cfg.selected_categories:
				continue
			self.per_app_categories[app][category].addTest(test)

	def _prepare_integration(self, suite: unittest.TestSuite, app: str) -> None:
		"""Prepare the environment for integration tests."""
		if not self.cfg.skip_before_tests:
			self._run_before_test_hooks(app)
		else:
			logger.debug("Skipping before_tests hooks: Explicitly skipped")

		if app:
			self._create_global_test_record_dependencies(app)

	@staticmethod
	@debug_timer
	def _run_before_test_hooks(config: TestConfig, app: str | None):
		"""Run 'before_tests' hooks"""
		logger.debug('Running "before_tests" hooks')
		for hook_function in frappe.get_hooks("before_tests", app_name=app):
			frappe.get_attr(hook_function)()

	@staticmethod
	@debug_timer
	def _create_global_test_record_dependencies(app: str | None):
		"""Create global test record dependencies"""
		test_module = frappe.get_module(f"{app}.tests")
		if hasattr(test_module, "global_test_dependencies"):
			logger.info("Creating global test record dependencies ...")
			for doctype in test_module.global_test_dependencies:
				logger.debug(f"Creating global test records for {doctype}")
				make_test_records(doctype, commit=True)

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
			verbosity=2 if logger.getEffectiveLevel() < logging.INFO else 1,
			tb_locals=logger.getEffectiveLevel() <= logging.INFO,
			cfg=test_config,
		)

		if doctype or doctype_list_path:
			doctype = _load_doctype_list(doctype_list_path) if doctype_list_path else doctype
			results = _run_doctype_tests(doctype, runner, force, app)
		elif module_def:
			results = _run_module_def_tests(app, module_def, runner, force)
		elif module:
			results = _run_module_tests(module, runner, app)
		else:
			apps = [app] if app else frappe.get_installed_apps()
			results = _run_all_tests(apps, runner)

		# Determine overall success by checking if any test suite failed
		success = all(result.wasSuccessful() for _, result in results)
		click.secho("\nTest Results:", fg="cyan", bold=True)

		def _print_result(category, result):
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

		for category, result in results:
			_print_result(category.title(), result)

		if success:
			click.echo(f"\n{click.style('All tests passed successfully!', fg='green', bold=True)}")
		else:
			click.echo(f"\n{click.style('Some tests failed or encountered errors.', fg='red', bold=True)}")

		if not success:
			sys.exit(1)

		return results

	finally:
		_cleanup_after_tests()
		if xml_output_file:
			xml_output_file.close()

		end_time = time.time()
		logger.debug(f"Total test run time: {end_time - start_time:.3f} seconds")


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
	app, module_def, runner: TestRunner, force
) -> tuple[unittest.TestResult, unittest.TestResult | None]:
	"""Run tests for the specified module definition"""
	doctypes = _get_doctypes_for_module_def(app, module_def)
	return _run_doctype_tests(doctypes, runner, force, app)


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
def _run_all_tests(apps: list[str], runner: TestRunner) -> list[unittest.TestResult]:
	"""Run all tests for the specified app or all installed apps"""
	logger.debug(f"Running tests for apps: {apps}")
	try:
		for current_app in apps:
			logger.debug(f"Running tests for app: {current_app}")
			return runner.discover_tests(current_app).run()
	except Exception as e:
		logger.error(f"Error running all tests for {apps or 'all apps'}: {e!s}")
		raise TestRunnerError(f"Failed to run tests for {apps or 'all apps'}: {e!s}") from e


@debug_timer
def _run_doctype_tests(
	doctypes, runner: TestRunner, force=False, app: str | None = None
) -> list[unittest.TestResult]:
	"""Run tests for the specified doctype(s)"""
	try:
		return runner.discover_doctype_tests(doctypes, app, force).run()
	except Exception as e:
		logger.error(f"Error running tests for doctypes {doctypes}: {e!s}")
		raise TestRunnerError(f"Failed to run tests for doctypes: {e!s}") from e


@debug_timer
def _run_module_tests(module, runner: TestRunner, app: str | None = None) -> list[unittest.TestResult]:
	"""Run tests for the specified module"""
	try:
		return runner.discover_module_tests(module, app).run()
	except Exception as e:
		logger.error(f"Error running tests for module {module}: {e!s}")
		raise TestRunnerError(f"Failed to run tests for module: {e!s}") from e


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
