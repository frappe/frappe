<<<<<<< HEAD
""" Utils for deprecating functionality in Framework.
=======
"""Utils for deprecating functionality in Framework.
>>>>>>> beab110ce9 (fix: clarify error message for child tables)

WARNING: This file is internal, instead of depending just copy the code or use deprecation
libraries.
"""
<<<<<<< HEAD
import functools
import warnings


def deprecated(func):
	"""Decorator to wrap a function/method as deprecated."""

	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		deprecation_warning(
			f"{func.__name__} is deprecated and will be removed in next major version.",
			stacklevel=1,
		)
		return func(*args, **kwargs)

	return wrapper


def deprecation_warning(message, category=DeprecationWarning, stacklevel=1):
	"""like warnings.warn but with auto incremented sane stacklevel."""

	warnings.warn(message=message, category=category, stacklevel=stacklevel + 2)
=======

from frappe.deprecation_dumpster import (
	_old_deprecated as deprecated,
)
from frappe.deprecation_dumpster import (
	_old_deprecation_warning as deprecation_warning,
)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
