"""
Welcome to the Deprecation Dumpster: Where Old Code Goes to Party! 🎉🗑️

This file is the final resting place (or should we say, "retirement home"?) for all the deprecated functions and methods of the Frappe framework. It's like a code nursing home, but with more monkey-patching and less bingo.

Each function or method that checks in here comes with its own personalized decorator, complete with:
1. The date it was marked for deprecation (its "over the hill" birthday)
2. The Frappe version in which it will be removed (its "graduation" to the great codebase in the sky)
3. A user-facing note on alternative solutions (its "parting wisdom")

Warning: The global namespace herein is more patched up than a sailor's favorite pair of jeans. Proceed with caution and a sense of humor!

Remember, deprecated doesn't mean useless - it just means these functions are enjoying their golden years before their final bow. Treat them with respect, and maybe bring them some virtual prune juice.

Enjoy your stay in the Deprecation Dumpster, where every function gets a second chance to shine (or at least, to not break everything).
"""

import inspect
import os
import sys
import warnings


def is_tty():
	return sys.stdout.isatty()


def colorize(text, color_code):
	if is_tty():
		return f"\033[{color_code}m{text}\033[0m"
	return text


try:
	# since python 3.13, PEP 702
	from warnings import deprecated as _deprecated
except Exception:
	import functools
	import warnings
	from collections.abc import Callable
	from typing import Optional, TypeVar, Union, overload

	T = TypeVar("T", bound=Callable)

	def _deprecated(message: str, category=DeprecationWarning, stacklevel=1) -> Callable[[T], T]:
		def decorator(func: T) -> T:
			@functools.wraps(func)
			def wrapper(*args, **kwargs):
				if message:
					warning_msg = f"{func.__name__} is deprecated.\n{message}"
				else:
					warning_msg = f"{func.__name__} is deprecated."
				warnings.warn(warning_msg, category=category, stacklevel=stacklevel + 1)
				return func(*args, **kwargs)

			return wrapper
			wrapper.__deprecated__ = True  # hint for the type checker

		return decorator


def deprecated(original: str, marked: str, graduation: str, msg: str, stacklevel: int = 1):
	"""Decorator to wrap a function/method as deprecated.

	Arguments:
	        - original: frappe.utils.make_esc  (fully qualified)
	        - marked: 2024-09-13  (the date it has been marked)
	        - graduation: v17  (generally: current version + 2)
	"""

	def decorator(func):
		# Get the filename of the caller
		frame = inspect.currentframe()
		caller_filepath = frame.f_back.f_code.co_filename
		if os.path.basename(caller_filepath) != "deprecation_dumpster.py":
			raise RuntimeError(
				colorize("The deprecated function ", "93")
				+ colorize(func.__name__, "96")
				+ colorize(" can only be called from ", "93")
				+ colorize("frappe/deprecation_dumpster.py\n", "96")
				+ colorize("Move the entire function there and import it back via adding\n ", "93")  # yellow
				+ colorize(f"from frappe.deprecation_dumpster import {func.__name__}\n", "96")  # cyan
				+ colorize("to file\n ", "93")  # yellow
				+ colorize(caller_filepath, "96")  # cyan
			)

		return functools.wraps(func)(
			_deprecated(
				colorize(f"`{original}`", "96")
				+ colorize(
					f" was moved (DATE: {marked}) to frappe/deprecation_dumpster.py"
					f" for removal (from {graduation} onwards); note:\n ",
					"91",
				)  # red
				+ colorize(f"{msg}\n", "93"),  # yellow
				stacklevel=stacklevel,
			)
		)(func)

	return decorator


def deprecation_warning(marked: str, graduation: str, msg: str):
	"""Warn in-place from a deprecated code path, for objects use `@deprecated` decorator from the deprectation_dumpster"

	Arguments:
	        - marked: 2024-09-13  (the date it has been marked)
	        - graduation: v17  (generally: current version + 2)
	"""

	warnings.warn(
		colorize(
			f"This codepath was marked (DATE: {marked}) deprecated"
			f" for removal (from {graduation} onwards); note:\n ",
			"91",
		)  # red
		+ colorize(f"{msg}\n", "93"),  # yellow
		category=DeprecationWarning,
		stacklevel=2,
	)


### Party starts here
def _old_deprecated(func):
	return deprecated(
		"frappe.deprecations.deprecated",
		"2024-09-13",
		"v17",
		"Make use of the frappe/deprecation_dumpster.py file, instead. 🎉🗑️",
	)(_deprecated("")(func))


def _old_deprecation_warning(msg):
	@deprecated(
		"frappe.deprecations.deprecation_warning",
		"2024-09-13",
		"v17",
		"Use frappe.deprecation_dumpster.deprecation_warning, instead. 🎉🗑️",
	)
	def deprecation_warning(message, category=DeprecationWarning, stacklevel=1):
		warnings.warn(message=message, category=category, stacklevel=stacklevel + 2)

	return deprecation_warning(msg)


@deprecated("frappe.utils.make_esc", "unknown", "v17", "Not used anymore.")
def make_esc(esc_chars):
	"""
	Function generator for Escaping special characters
	"""
	return lambda s: "".join("\\" + c if c in esc_chars else c for c in s)
