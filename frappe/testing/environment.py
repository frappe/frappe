"""
This module handles the setup and teardown of the test environment for Frappe applications.

Key components:
- _initialize_test_environment: Initializes the test environment for a given site
- _cleanup_after_tests: Performs cleanup operations after running tests
- _disable_scheduler_if_needed: Disables the scheduler if it's not already disabled
- IntegrationTestPreparation: A class to prepare the environment for integration tests

The module provides functionality for:
- Initializing the database connection
- Setting test-related flags
- Disabling the scheduler during tests
- Running 'before_tests' hooks
- Creating global test record dependencies

Usage:
These functions and classes are typically used by the test runner to set up
and tear down the test environment before and after test execution.
"""

import functools
import inspect
import logging
import unittest

import tomllib

import frappe
import frappe.utils.scheduler
from frappe.tests.utils import make_test_records

from .runner import TestRunnerError
from .utils import debug_timer

logger = logging.getLogger(__name__)


@debug_timer
def _initialize_test_environment(site, config):
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

	_decorate_all_methods_and_functions_with_type_checker()


def _cleanup_after_tests():
	"""Perform cleanup operations after running tests"""
	global scheduler_disabled_by_user
	if not scheduler_disabled_by_user:
		frappe.utils.scheduler.enable_scheduler()

	if frappe.db:
		# this commit ends the transaction
		frappe.db.commit()  # nosemgrep
		frappe.clear_cache()


# Global variable to track scheduler state
scheduler_disabled_by_user = False


def _disable_scheduler_if_needed():
	"""Disable scheduler if it's not already disabled"""
	global scheduler_disabled_by_user
	scheduler_disabled_by_user = frappe.utils.scheduler.is_scheduler_disabled(verbose=False)
	if not scheduler_disabled_by_user:
		frappe.utils.scheduler.disable_scheduler()


@debug_timer
def _decorate_all_methods_and_functions_with_type_checker():
	from frappe.utils.typing_validations import validate_argument_types

	def _get_config_from_pyproject(app_path):
		try:
			with open(f"{app_path}/pyproject.toml", "rb") as f:
				config = tomllib.load(f)
				return (
					config.get("tool", {})
					.get("frappe", {})
					.get("testing", {})
					.get("function_type_validation", {})
				)
		except FileNotFoundError:
			return {}
		except tomllib.TOMLDecodeError:
			logger.warning(f"Failed to parse pyproject.toml for app {app_path}")
			return {}

	def _decorate_callable(obj, apps, parent_module):
		# whitelisted methods are already checked, see frappe.whitelist
		if getattr(obj, "__func__", obj) in frappe.whitelisted:
			return obj
		# Check if the function is already decorated
		elif hasattr(obj, "_is_decorated_for_validate_argument_types"):
			return obj
		elif module := getattr(obj, "__module__", ""):
			if (app := module.split(".", 1)[0]) and app not in apps:
				return obj
			config = _get_config_from_pyproject(frappe.get_app_source_path(app))
			skip_namespaces = config.get("skip_namespaces", [])
			if any(module.startswith(n) for n in skip_namespaces):
				return obj

		@functools.wraps(obj)
		def wrapper(*args, **kwargs):
			try:
				return validate_argument_types(obj)(*args, **kwargs)
			except TypeError as e:
				# breakpoint()
				raise e

		wrapper._is_decorated_for_validate_argument_types = True

		logger.debug(f"... patching {obj.__module__}.{obj.__name__} in {parent_module.__name__}")

		return wrapper

	def _decorate_module(module, apps, current_depth, max_depth):
		if current_depth >= max_depth:
			return
		if (app := module.__name__.split(".", 1)[0]) and app not in apps:
			return
		for name in dir(module):
			obj = getattr(module, name)
			if inspect.isfunction(obj):
				if not hasattr(obj, "__annotations__"):
					continue
				setattr(module, name, _decorate_callable(obj, apps, module))
			elif inspect.ismodule(obj):
				if hasattr(obj, "_is_decorated_for_validate_argument_types"):
					continue
				obj._is_decorated_for_validate_argument_types = True
				_decorate_module(obj, apps, current_depth + 1, max_depth)

	for app in (apps := frappe.get_installed_apps()):
		config = _get_config_from_pyproject(frappe.get_app_source_path(app))
		max_depth = config.get("max_module_depth", float("inf"))
		logger.info(
			f"Decorating callables with type validator up to module depth {max_depth+1} in {app!r} ..."
		)
		for module_name in frappe.local.app_modules.get(app) or []:
			try:
				module = frappe.get_module(f"{app}.{module_name}")
				_decorate_module(module, apps, 0, max_depth)
			except ImportError:
				logger.error(f"Error importing module {app}.{module_name}")


class IntegrationTestPreparation:
	def __init__(self, cfg):
		self.cfg = cfg

	def __call__(self, suite: unittest.TestSuite, app: str, category: str) -> None:
		"""Prepare the environment for integration tests."""
		if not self.cfg.skip_before_tests:
			self._run_before_test_hooks(app, category)
		else:
			logger.debug("Skipping before_tests hooks: Explicitly skipped")

		self._create_global_test_record_dependencies(app, category)

	@staticmethod
	@debug_timer
	def _run_before_test_hooks(app: str, category: str):
		"""Run 'before_tests' hooks"""
		logger.info(f'Running "before_tests" hooks for {category} tests on app: {app}')
		for hook_function in frappe.get_hooks("before_tests", app_name=app):
			logger.info(f'Running "before_tests" hook function {hook_function}')
			frappe.get_attr(hook_function)()

	@staticmethod
	@debug_timer
	def _create_global_test_record_dependencies(app: str, category: str):
		"""Create global test record dependencies"""
		try:
			test_module = frappe.get_module(f"{app}.tests")
			if hasattr(test_module, "global_test_dependencies"):
				logger.info(f"Creating global test record dependencies for {category} tests on {app} ...")
				for doctype in test_module.global_test_dependencies:
					logger.debug(f"Creating global test records for {doctype}")
					make_test_records(doctype, commit=True)
		except ModuleNotFoundError:
			pass
