from functools import wraps
from typing import Any, Callable, TypeVar

import frappe

T = TypeVar("T", bound=Callable[..., Any])


def memoize(fn: T, ttl: int = 600) -> T:
	"""A decorator to memoize function results into redis cache."""

	cache = frappe.cache()

	@wraps(fn)
	def wrapper(*args: Any, **kwargs: Any):
		key = __create_key(fn, *args, **kwargs)
		return cache.get_value(key, generator=lambda: fn(*args, **kwargs))

	return wrapper


def __create_key(fn, *args, **kwargs):
	return (
		fn.__name__
		+ "|"
		+ ",".join(str(arg) for arg in args)
		+ "|"
		+ ",".join(f"{key}:{value}" for key, value in kwargs.items())
	)
