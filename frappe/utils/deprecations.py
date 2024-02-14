""" Utils for deprecating functionality in Framework.

WARNING: This file is internal, instead of depending just copy the code or use deprecation
libraries.
"""
import functools
import warnings


def deprecated(func, reason=None):
	"""Decorator to wrap a function/method as deprecated."""

	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		msg = f"{func.__name__} is deprecated and will be removed in next major version."
		if reason:
			msg += f" Reason: {reason}"
		deprecation_warning(msg, stacklevel=1)
		return func(*args, **kwargs)

	return wrapper


def deprecation_warning(message, category=DeprecationWarning, stacklevel=1):
	"""like warnings.warn but with auto incremented sane stacklevel."""

	warnings.warn(message=message, category=category, stacklevel=stacklevel + 2)
