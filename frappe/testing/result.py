"""
This module contains the TestResult class, which extends unittest.TextTestResult
to provide custom formatting and logging for test results in the Frappe framework.

Key components:
- TestResult: The main class for handling test results
- SLOW_TEST_THRESHOLD: A constant defining the threshold for slow tests

The TestResult class provides:
- Custom output formatting for different test outcomes (success, failure, error, skip)
- Timing information for each test, with highlighting for slow tests
- Logging of test results for debugging purposes
- Custom error reporting

Usage:
This TestResult class is typically used by the TestRunner to collect and display
test results during test execution in the Frappe framework.
"""

import logging
import time
import unittest

import click

logger = logging.getLogger(__name__)


class TestResult(unittest.TextTestResult):
	def startTest(self, test):
		self.tb_locals = True
		self._started_at = time.monotonic()
		super(unittest.TextTestResult, self).startTest(test)
		test_class = unittest.util.strclass(test.__class__)
		if getattr(self, "current_test_class", None) != test_class:
			self.current_test_class = test_class
			click.echo(f"\n{unittest.util.strclass(test.__class__)}")
			logger.info(f"{unittest.util.strclass(test.__class__)}")
			if new_doctypes := getattr(test.__class__, "_newly_created_test_records", None):
				records = [f"{name} ({qty})" for name, qty in reversed(new_doctypes)]
				click.secho(
					f"  Test Records created: {', '.join(records)}",
					fg="bright_black",
				)
				logger.info(f"records created: {', '.join(records)}")

	def getTestMethodName(self, test):
		return test._testMethodName if hasattr(test, "_testMethodName") else str(test)

	def addSuccess(self, test):
		super(unittest.TextTestResult, self).addSuccess(test)
		elapsed = time.monotonic() - self._started_at
		threshold_passed = elapsed >= SLOW_TEST_THRESHOLD
		long_elapsed = click.style(f" ({elapsed:.03}s)", fg="red") if threshold_passed else ""
		click.echo(f"  {click.style(' ✔ ', fg='green')} {self.getTestMethodName(test)}{long_elapsed}")
		logger.debug(f"{test!s:<200} {'[success]':>20} ⌛{elapsed}")

	def addError(self, test, err):
		super(unittest.TextTestResult, self).addError(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")
		logger.debug(f"{test!s:<200} {'[error]':>20}")

	def addFailure(self, test, err):
		super(unittest.TextTestResult, self).addFailure(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")
		logger.debug(f"{test!s:<200} {'[failure]':>20}")

	def addSkip(self, test, reason):
		super(unittest.TextTestResult, self).addSkip(test, reason)
		click.echo(f"  {click.style(' = ', fg='white')} {self.getTestMethodName(test)}")
		logger.debug(f"{test!s:<200} {'[skipped]':>20}")

	def addExpectedFailure(self, test, err):
		super(unittest.TextTestResult, self).addExpectedFailure(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")
		logger.debug(f"{test!s:<200} {'[expected failure]':>20}")

	def addUnexpectedSuccess(self, test):
		super(unittest.TextTestResult, self).addUnexpectedSuccess(test)
		click.echo(f"  {click.style(' ✔ ', fg='green')} {self.getTestMethodName(test)}")
		logger.debug(f"{test!s:<200} {'[unexpected success]':>20}")

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


SLOW_TEST_THRESHOLD = 2
