"""
This module contains the TestRunner class, which is responsible for executing test suites in Frappe.

The TestRunner class extends unittest.TextTestRunner and provides additional functionality:
- Categorization of tests (unit, integration, functional)
- Priority-based execution of test categories
- Profiling capabilities
- Integration with Frappe's configuration and environment setup

Key components:
- TestRunner: The main class for running tests
- CATEGORY_PRIORITIES: A dictionary defining the execution order of test categories
- Various utility methods for test preparation, profiling, and iteration

Usage:
The TestRunner is typically instantiated and used by Frappe's test discovery and execution system.
It can be customized through the TestConfig object passed during initialization.

"""

import contextlib
import cProfile
import logging
import pstats
import unittest
from collections import defaultdict
from collections.abc import Iterator
from io import StringIO

from frappe.tests.classes.context_managers import debug_on

from .config import TestConfig
from .discovery import TestRunnerError
from .environment import IntegrationTestPreparation
from .result import TestResult

logger = logging.getLogger(__name__)

# Define category priorities
CATEGORY_PRIORITIES = {
	"unit": 1,
	"integration": 2,
	"functional": 3,
	# Add more categories and their priorities as needed
}


class TestRunner(unittest.TextTestRunner):
	def __init__(
		self,
		stream=None,
		descriptions=True,
		verbosity=1,
		failfast=False,
		buffer=True,
		resultclass=None,
		warnings="module",
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
			resultclass=resultclass or TestResult,
			warnings=warnings,
			tb_locals=tb_locals,
		)
		self.cfg = cfg
		self.per_app_categories = defaultdict(lambda: defaultdict(unittest.TestSuite))
		self.integration_preparation = IntegrationTestPreparation(cfg)
		logger.debug("TestRunner initialized")

	def iterRun(self) -> Iterator[tuple[str, str, unittest.TestSuite]]:
		for app, categories in self.per_app_categories.items():
			sorted_categories = sorted(
				categories.items(), key=lambda x: CATEGORY_PRIORITIES.get(x[0], float("inf"))
			)
			for category, suite in sorted_categories:
				if not self._has_tests(suite):
					logger.debug(f"no tests for: {app}, {category}")
					continue

				self._prepare_category(category, suite, app)
				self._apply_debug_decorators(suite)

				with self._profile():
					logger.info(f"Starting tests for app: {app}, category: {category}")
					yield app, category, suite

	def _has_tests(self, suite):
		return next(self._iterate_suite(suite), None) is not None

	def _prepare_category(self, category, suite, app):
		from frappe.deprecation_dumpster import get_compat_frappe_test_case_preparation

		dispatcher = {
			"integration": self.integration_preparation,
			"old-frappe-test-class-category": get_compat_frappe_test_case_preparation(self.cfg),
			# Add other categories here as needed
		}
		prepare_method = dispatcher.get(category.lower())
		if prepare_method:
			prepare_method(suite, app, category)
		else:
			logger.debug(f"Unknown test category: {category}. No specific preparation performed.")

	def _apply_debug_decorators(self, suite):
		if self.cfg.pdb_on_exceptions:
			for test in self._iterate_suite(suite):
				setattr(
					test,
					test._testMethodName,
					debug_on(*self.cfg.pdb_on_exceptions)(getattr(test, test._testMethodName)),
				)

	@contextlib.contextmanager
	def _profile(self):
		if self.cfg.profile:
			logger.debug("profiling enabled")
			pr = cProfile.Profile()
			pr.enable()
		yield
		if self.cfg.profile:
			pr.disable()
			s = StringIO()
			ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
			ps.print_stats()
			print(s.getvalue())

	@staticmethod
	def _iterate_suite(suite):
		for test in suite:
			if isinstance(test, unittest.TestSuite):
				yield from TestRunner._iterate_suite(test)
			elif isinstance(test, unittest.TestCase):
				yield test
