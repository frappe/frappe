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
from functools import cache
from importlib import reload
from io import StringIO
from pathlib import Path
from typing import Optional, Union

import frappe
import frappe.utils.scheduler
from frappe.model.naming import revert_series_if_last
from frappe.modules import get_module_name, load_doctype_module
from frappe.tests.utils import FrappeIntegrationTestCase
from frappe.utils import cint

unittest_runner = unittest.TextTestRunner
SLOW_TEST_THRESHOLD = 2


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
	skip_test_records: bool = False,
	skip_before_tests: bool = False,
	pdb_on_exceptions: bool = False,
) -> None:
	"""Main function to run tests"""
	global unittest_runner

	logger.setLevel(logging.DEBUG if verbose else logging.INFO)

	test_config = TestConfig(
		profile=profile,
		failfast=failfast,
		junit_xml_output=bool(junit_xml_output),
		tests=tests,
		case=case,
		pdb_on_exceptions=pdb_on_exceptions,
	)

	_initialize_test_environment(site, skip_before_tests, skip_test_records)

	xml_output_file = _setup_xml_output(junit_xml_output)

	try:
		scheduler_disabled_by_user = _disable_scheduler_if_needed()

		if not frappe.flags.skip_before_tests:
			_run_before_test_hooks(test_config, app)

		if doctype or doctype_list_path:
			doctype = _load_doctype_list(doctype_list_path) if doctype_list_path else doctype
			test_result = _run_doctype_tests(doctype, test_config, force)
		elif module_def:
			test_result = _run_module_def_tests(app, module_def, test_config, force)
		elif module:
			test_result = _run_module_tests(module, test_config)
		else:
			test_result = _run_all_tests(app, test_config)

		_cleanup_after_tests(scheduler_disabled_by_user)

		print_test_categories(test_config)  # Add this line

		_cleanup_after_tests(scheduler_disabled_by_user)

		return test_result

	finally:
		if xml_output_file:
			xml_output_file.close()


def print_test_categories(config: TestConfig):
	"""Print the categorized tests"""
	logger.info("Test Categories:")
	logger.info(f" Unit Tests: {len(config.categories['unit'])}")
	logger.info(f" Integration Tests: {len(config.categories['integration'])}")


def _initialize_test_environment(site, skip_before_tests, skip_test_records):
	"""Initialize the test environment"""
	frappe.init(site)
	if not frappe.db:
		frappe.connect()

	frappe.flags.skip_before_tests = skip_before_tests
	frappe.flags.skip_test_records = skip_test_records

	# Set various test-related flags
	frappe.flags.in_test = True
	frappe.flags.print_messages = logger.getEffectiveLevel() < logging.INFO
	frappe.flags.tests_verbose = logger.getEffectiveLevel() < logging.INFO
	frappe.clear_cache()


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


def _disable_scheduler_if_needed():
	"""Disable scheduler if it's not already disabled"""
	scheduler_disabled_by_user = frappe.utils.scheduler.is_scheduler_disabled(verbose=False)
	if not scheduler_disabled_by_user:
		frappe.utils.scheduler.disable_scheduler()
	return scheduler_disabled_by_user


def _run_before_test_hooks(test_config, app):
	"""Run 'before_tests' hooks if not skipped by the caller"""
	logger.debug('Running "before_tests" hooks')
	for hook_function in frappe.get_hooks("before_tests", app_name=app):
		frappe.get_attr(hook_function)()


def _load_doctype_list(doctype_list_path):
	"""Load the list of doctypes from the specified file"""
	app, path = doctype_list_path.split(os.path.sep, 1)
	with open(frappe.get_app_path(app, path)) as f:
		return f.read().strip().splitlines()


def _run_module_def_tests(app, module_def, test_config, force):
	"""Run tests for the specified module definition"""
	doctypes = _get_doctypes_for_module_def(app, module_def)
	return _run_doctype_tests(doctypes, test_config, force)


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


def _cleanup_after_tests(scheduler_disabled_by_user):
	"""Perform cleanup operations after running tests"""
	if not scheduler_disabled_by_user:
		frappe.utils.scheduler.enable_scheduler()

	if frappe.db:
		frappe.db.commit()

	frappe.clear_cache()


class TimeLoggingTestResult(unittest.TextTestResult):
	"""Custom TestResult class for logging test execution time"""

	def startTest(self, test):
		self._started_at = time.monotonic()
		super().startTest(test)

	def addSuccess(self, test):
		elapsed = time.monotonic() - self._started_at
		name = self.getDescription(test)
		if elapsed >= SLOW_TEST_THRESHOLD:
			self.stream.write(f"\n{name} ({elapsed:.03}s)\n")
		super().addSuccess(test)


def _run_all_tests(app: str | None, config: TestConfig) -> unittest.TestResult:
	"""Run all tests for the specified app or all installed apps"""
	apps = [app] if app else frappe.get_installed_apps()
	test_suite = unittest.TestSuite()

	for app in apps:
		app_path = Path(frappe.get_app_path(app))
		for path in app_path.rglob("test_*.py"):
			if path.name != "test_runner.py":
				relative_path = path.relative_to(app_path)
				if not any(
					part in relative_path.parts for part in ["locals", ".git", "public", "__pycache__"]
				):
					_add_test(app_path, path, test_suite)

	runner = unittest_runner(
		resultclass=TimeLoggingTestResult if not config.junit_xml_output else None,
		verbosity=2 if logger.getEffectiveLevel() < logging.INFO else 1,
		failfast=config.failfast,
		tb_locals=logger.getEffectiveLevel() < logging.DEBUG,
	)

	if config.profile:
		pr = cProfile.Profile()
		pr.enable()

	out = runner.run(test_suite)

	if config.profile:
		pr.disable()
		s = StringIO()
		pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats()
		print(s.getvalue())

	return out


def _run_doctype_tests(doctypes, config: TestConfig, force=False):
	"""Run tests for the specified doctype(s)"""
	try:
		modules = []
		doctypes = [doctypes] if not isinstance(doctypes, list | tuple) else doctypes

		for doctype in doctypes:
			module = frappe.db.get_value("DocType", doctype, "module")
			if not module:
				raise TestRunnerError(f"Invalid doctype {doctype}")

			test_module = get_module_name(doctype, module, "test_")
			if force:
				frappe.db.delete(doctype)
			make_test_records(doctype, force=force, commit=True)
			modules.append(importlib.import_module(test_module))

		return _run_unittest(modules, config=config)
	except Exception as e:
		logger.error(f"Error running tests for doctypes {doctypes}: {e!s}")
		raise TestRunnerError(f"Failed to run tests for doctypes: {e!s}") from e


def _run_module_tests(module, config: TestConfig):
	"""Run tests for the specified module"""
	module = importlib.import_module(module)
	if hasattr(module, "test_dependencies"):
		for doctype in module.test_dependencies:
			make_test_records(doctype, commit=True)

	frappe.db.commit()
	return _run_unittest(module, config=config)


def _run_unittest(modules, config: TestConfig):
	"""Run unittest for the specified module(s)"""
	frappe.db.begin()
	modules = [modules] if not isinstance(modules, list | tuple) else modules
	final_test_suite = unittest.TestSuite()

	for module in modules:
		test_suite = unittest.TestLoader().loadTestsFromModule(module)
		if config.case:
			test_suite = unittest.TestLoader().loadTestsFromTestCase(getattr(module, config.case))

		for test in _iterate_suite(test_suite):
			if config.tests and test._testMethodName not in config.tests:
				continue

			if isinstance(test, FrappeIntegrationTestCase):
				config.categories["integration"].append(test)
			else:
				config.categories["unit"].append(test)

			final_test_suite.addTest(test)

	if config.pdb_on_exceptions:
		for test_case in _iterate_suite(final_test_suite):
			if hasattr(test_case, "_apply_debug_decorator"):
				test_case._apply_debug_decorator(config.pdb_on_exceptions)

	runner = unittest_runner(
		resultclass=None if config.junit_xml_output else TimeLoggingTestResult,
		verbosity=2 if logger.getEffectiveLevel() < logging.INFO else 1,
		failfast=config.failfast,
		tb_locals=logger.getEffectiveLevel() < logging.DEBUG,
	)

	if config.profile:
		pr = cProfile.Profile()
		pr.enable()

	out = runner.run(final_test_suite)

	if config.profile:
		pr.disable()
		s = StringIO()
		ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
		ps.print_stats()
		print(s.getvalue())

	return out


def _iterate_suite(suite):
	"""Helper function to iterate through a test suite"""
	for test in suite:
		if isinstance(test, unittest.TestSuite):
			yield from _iterate_suite(test)
		elif isinstance(test, unittest.TestCase):
			yield test


def _add_test(app_path: Path, path: Path, test_suite: unittest.TestSuite | None = None) -> None:
	relative_path = path.relative_to(app_path)

	if path.parts[-4:-1] == ("doctype", "doctype", "boilerplate"):
		return  # Skip boilerplate files

	module_name = (
		f"{app_path.stem}.{'.'.join(relative_path.parent.parts)}.{path.stem}"
		if str(relative_path.parent) != "."
		else f"{app_path.stem}.{path.stem}"
	)
	module = importlib.import_module(module_name)

	if hasattr(module, "test_dependencies"):
		for doctype in module.test_dependencies:
			make_test_records(doctype, commit=True)

	test_suite = test_suite or unittest.TestSuite()

	if path.parent.name == "doctype":
		json_file = path.with_name(path.stem[5:] + ".json")
		if json_file.exists():
			with json_file.open() as f:
				doctype = json.loads(f.read())["name"]
			make_test_records(doctype, commit=True)

	test_suite.addTest(unittest.TestLoader().loadTestsFromModule(module))


def make_test_records(doctype, force=False, commit=False):
	"""Make test records for the specified doctype"""
	if frappe.flags.skip_test_records:
		return

	for options in get_dependencies(doctype):
		if options == "[Select]":
			continue

		if options not in frappe.local.test_objects:
			frappe.local.test_objects[options] = []
			make_test_records(options, force, commit=commit)
			make_test_records_for_doctype(options, force, commit=commit)


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

	options_list = [df.options for df in link_fields] + [doctype]

	if hasattr(test_module, "test_dependencies"):
		options_list += test_module.test_dependencies

	options_list = list(set(options_list))

	if hasattr(test_module, "test_ignore"):
		for doctype_name in test_module.test_ignore:
			if doctype_name in options_list:
				options_list.remove(doctype_name)

	options_list.sort()

	return options_list


def make_test_records_for_doctype(doctype, force=False, commit=False):
	"""Make test records for the specified doctype"""
	test_record_log_instance = TestRecordLog()
	if not force and doctype in test_record_log_instance.get():
		return

	module, test_module = get_modules(doctype)
	logger.debug(f"Making test records for {doctype}")

	if hasattr(test_module, "_make_test_records"):
		frappe.local.test_objects[doctype] = (
			frappe.local.test_objects.get(doctype, []) + test_module._make_test_records()
		)
	elif hasattr(test_module, "test_records"):
		frappe.local.test_objects[doctype] = frappe.local.test_objects.get(doctype, []) + make_test_objects(
			doctype, test_module.test_records, force, commit=commit
		)
	else:
		test_records = frappe.get_test_records(doctype)
		if test_records:
			frappe.local.test_objects[doctype] = frappe.local.test_objects.get(
				doctype, []
			) + make_test_objects(doctype, test_records, force, commit=commit)
		elif logger.getEffectiveLevel() < logging.INFO:
			print_mandatory_fields(doctype)

	test_record_log_instance.add(doctype)


def make_test_objects(doctype, test_records=None, reset=False, commit=False):
	"""Make test objects from given list of `test_records` or from `test_records.json`"""
	records = []

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
				logger.DEBUG(f"Error in making test record for {d.doctype} {d.name}")
				raise

		records.append(d.name)

		if commit:
			frappe.db.commit()
	return records


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


# Compatibility functions
def add_to_test_record_log(doctype):
	TestRecordLog().add(doctype)


def get_test_record_log():
	return TestRecordLog().get()
