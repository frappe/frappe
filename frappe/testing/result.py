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

import io
import logging
import sys
import time
import unittest

import click

logger = logging.getLogger(__name__)


class TestResult(unittest.TextTestResult):
	def __init__(self, stream, descriptions, verbosity):
		super().__init__(stream, descriptions, verbosity)
		self._old_stdout = []
		self._old_stderr = []

	def _setupStdout(self):
		pass

	def _restoreStdout(self):
		pass

	def startTestRun(self):
		if not sys.warnoptions:
			import warnings

			from frappe.deprecation_dumpster import FrappeDeprecationWarning

			warnings.simplefilter("ignore")
			warnings.filterwarnings("module", category=FrappeDeprecationWarning)

		# capture class & module setup & teardown in order to show it above the first test of the class
		if self.buffer:
			self._old_stderr.append(sys.stderr)
			self._old_stdout.append(sys.stdout)
			self._module_or_class_stdout_capture = io.StringIO()
			self._module_or_class_stderr_capture = io.StringIO()
			sys.stdout = self._module_or_class_stdout_capture
			sys.stderr = self._module_or_class_stderr_capture

	def stopTestRun(self):
		if self.buffer:
			sys.stdout = self._old_stdout.pop()
			sys.stderr = self._old_stderr.pop()

	def startTest(self, test):
		self.tb_locals = True
		self._started_at = time.monotonic()
		super(unittest.TextTestResult, self).startTest(test)
		test_class = unittest.util.strclass(test.__class__)
		if getattr(self, "current_test_class", None) != test_class:
			self.current_test_class = test_class
			self.stream.write(f"\n{test_class}\n")
			logger.info(f"{test_class}")

			if hasattr(self, "_module_or_class_stdout_capture"):
				for line in self._module_or_class_stdout_capture.getvalue().splitlines():
					self.stream.write(click.style(f"  ▹ {line}\n", fg="bright_black"))
					self.stream.flush()
				self._module_or_class_stdout_capture.seek(0)
				self._module_or_class_stdout_capture.truncate()

			if hasattr(self, "_module_or_class_stderr_capture"):
				for line in self._module_or_class_stderr_capture.getvalue().splitlines():
					# self.stream.write(f"  ▸ {line}\n")
					self.stream.write(click.style(f"  ▸ {line}\n", fg="bright_black"))
					self.stream.flush()
				self._module_or_class_stderr_capture.seek(0)
				self._module_or_class_stderr_capture.truncate()

			if new_doctypes := getattr(test.__class__, "_newly_created_test_records", None):
				records = [f"{name} ({qty})" for name, qty in reversed(new_doctypes)]
				hint = click.style(f"  Test Records created: {', '.join(records)}", fg="bright_black")
				self.stream.write(hint + "\n")
				logger.info(f"records created: {', '.join(records)}")
			self.stream.flush()

		if self.buffer:
			self._old_stderr.append(sys.stderr)
			self._old_stdout.append(sys.stdout)
			self._test_stdout_capture = io.StringIO()
			self._test_stderr_capture = io.StringIO()
			sys.stdout = self._test_stdout_capture
			sys.stderr = self._test_stderr_capture

	def stopTest(self, test):
		super().stopTest(test)
		if self.buffer:
			sys.stdout = self._old_stderr.pop()
			sys.stderr = self._old_stdout.pop()
			for line in self._test_stdout_capture.getvalue().splitlines():
				self.stream.write(f"       ▹  {line}\n")
				self.stream.flush()
			for line in self._test_stderr_capture.getvalue().splitlines():
				self.stream.write(f"       ▸  {line}\n")
				self.stream.flush()

	def getTestMethodName(self, test):
		return test._testMethodName if hasattr(test, "_testMethodName") else str(test)

	def addSuccess(self, test):
		super(unittest.TextTestResult, self).addSuccess(test)
		elapsed = time.monotonic() - self._started_at
		threshold_passed = elapsed >= SLOW_TEST_THRESHOLD
		long_elapsed = click.style(f" ({elapsed:.03}s)", fg="red") if threshold_passed else ""
		self._write_result(test, " ✔ ", "green", long_elapsed)
		logger.debug(f"{test!s:<200} {'[success]':>20} ⌛{elapsed}")

	def addError(self, test, err):
		super(unittest.TextTestResult, self).addError(test, err)
		self._write_result(test, " ✖ ", "red")
		logger.debug(f"{test!s:<200} {'[error]':>20}")

	def addFailure(self, test, err):
		super(unittest.TextTestResult, self).addFailure(test, err)
		self._write_result(test, " ✖ ", "red")
		logger.debug(f"{test!s:<200} {'[failure]':>20}")

	def addSkip(self, test, reason):
		super(unittest.TextTestResult, self).addSkip(test, reason)
		self._write_result(test, " = ", "white")
		logger.debug(f"{test!s:<200} {'[skipped]':>20}")

	def addExpectedFailure(self, test, err):
		super(unittest.TextTestResult, self).addExpectedFailure(test, err)
		self.stream.write("x")
		self._write_result(test, "✔ ", "green")
		logger.debug(f"{test!s:<200} {'[expected failure]':>20}")

	def addUnexpectedSuccess(self, test):
		super(unittest.TextTestResult, self).addUnexpectedSuccess(test)
		self.stream.write("u")
		self._write_result(test, "✖ ", "red")
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

	def _write_result(self, test, status, color, suffix=""):
		test_method = self.getTestMethodName(test)
		result = f"   {click.style(status, fg=color)} {test_method}"
		result += f" {suffix}" if suffix else ""
		result += "\n"
		self.stream.write(result)
		self.stream.flush()


SLOW_TEST_THRESHOLD = 2


class FrappeTestResult(unittest.TextTestResult):
	def __init__(self, stream, descriptions, verbosity):
		super().__init__(stream, descriptions, verbosity)

	def startTest(self, test):
		self.tb_locals = True
		self._started_at = time.monotonic()
		super().startTest(test)
		super(unittest.TextTestResult, self).startTest(test)
		test_class = unittest.util.strclass(test.__class__)
		if not hasattr(self, "current_test_class") or self.current_test_class != test_class:
			click.echo(f"\n{unittest.util.strclass(test.__class__)}")
			self.current_test_class = test_class

	def getTestMethodName(self, test):
		return test._testMethodName if hasattr(test, "_testMethodName") else str(test)

	def addSuccess(self, test):
		super(unittest.TextTestResult, self).addSuccess(test)
		elapsed = time.monotonic() - self._started_at
		threshold_passed = elapsed >= SLOW_TEST_THRESHOLD
		elapsed = click.style(f" ({elapsed:.03}s)", fg="red") if threshold_passed else ""
		click.echo(f"  {click.style(' ✔ ', fg='green')} {self.getTestMethodName(test)}{elapsed}")

	def addError(self, test, err):
		super(unittest.TextTestResult, self).addError(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")

	def addFailure(self, test, err):
		super(unittest.TextTestResult, self).addFailure(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")

	def addSkip(self, test, reason):
		super(unittest.TextTestResult, self).addSkip(test, reason)
		click.echo(f"  {click.style(' = ', fg='white')} {self.getTestMethodName(test)}")

	def addExpectedFailure(self, test, err):
		super(unittest.TextTestResult, self).addExpectedFailure(test, err)
		click.echo(f"  {click.style(' ✖ ', fg='red')} {self.getTestMethodName(test)}")

	def addUnexpectedSuccess(self, test):
		super(unittest.TextTestResult, self).addUnexpectedSuccess(test)
		click.echo(f"  {click.style(' ✔ ', fg='green')} {self.getTestMethodName(test)}")
