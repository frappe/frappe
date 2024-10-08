import functools
import logging
import pdb
import signal
import sys
import traceback

logger = logging.Logger(__file__)


def debug_on(*exceptions):
	"""
	A decorator to automatically start the debugger when specified exceptions occur.

	This decorator allows you to automatically invoke the debugger (pdb) when certain
	exceptions are raised in the decorated function. If no exceptions are specified,
	it defaults to catching AssertionError.

	Args:
	        *exceptions: Variable length argument list of exception classes to catch.
	                If none provided, defaults to (AssertionError,).

	Returns:
	        function: A decorator function.

	Usage:
	        1. Basic usage (catches AssertionError):
	                @debug_on()
	                def test_assertion_error():
	                        assert False, "This will start the debugger"

	        2. Catching specific exceptions:
	                @debug_on(ValueError, TypeError)
	                def test_specific_exceptions():
	                        raise ValueError("This will start the debugger")

	        3. Using on a method in a test class:
	                class TestMyFunctionality(unittest.TestCase):
	                        @debug_on(ZeroDivisionError)
	                        def test_division_by_zero(self):
	                                result = 1 / 0

	Note:
	        When an exception is caught, this decorator will print the exception traceback
	        and then start the post-mortem debugger, allowing you to inspect the state of
	        the program at the point where the exception was raised.
	"""
	if not exceptions:
		exceptions = (AssertionError,)

	def decorator(f):
		@functools.wraps(f)
		def wrapper(*args, **kwargs):
			try:
				return f(*args, **kwargs)
			except exceptions as e:
				exc_type, exc_value, exc_traceback = sys.exc_info()
				# Pretty print the exception
				print("\n\033[91m" + "=" * 60 + "\033[0m")  # Red line
				print("\033[93m" + str(exc_type.__name__) + ": " + str(exc_value) + "\033[0m")
				print("\033[91m" + "=" * 60 + "\033[0m")  # Red line

				# Print the formatted traceback
				traceback_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
				for line in traceback_lines:
					print("\033[96m" + line.rstrip() + "\033[0m")  # Cyan color

				print("\033[91m" + "=" * 60 + "\033[0m")  # Red line
				print("\033[92mEntering post-mortem debugging\033[0m")
				print("\033[91m" + "=" * 60 + "\033[0m")  # Red line
				pdb.post_mortem()

				raise e

		return wrapper

	return decorator


def timeout(seconds=30, error_message="Test timed out."):
	"""Timeout decorator to ensure a test doesn't run for too long.

	adapted from https://stackoverflow.com/a/2282656"""

	# Support @timeout (without function call)
	no_args = bool(callable(seconds))
	actual_timeout = 30 if no_args else seconds
	actual_error_message = "Test timed out" if no_args else error_message

	def decorator(func):
		def _handle_timeout(signum, frame):
			raise Exception(actual_error_message)

		def wrapper(*args, **kwargs):
			signal.signal(signal.SIGALRM, _handle_timeout)
			signal.alarm(actual_timeout)
			try:
				result = func(*args, **kwargs)
			finally:
				signal.alarm(0)
			return result

		return wrapper

	if no_args:
		return decorator(seconds)

	return decorator
