# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. Check LICENSE

import time
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from types import NoneType

import frappe

_SITE_CACHE = defaultdict(dict)
_KWD_MARK = object()  # sentinel for separating args from kwargs


def __generate_request_cache_key(args: tuple, kwargs: dict) -> tuple:
	"""Generate a key for the cache."""
	assert isinstance(args, tuple), "args must be a tuple (from *args)"
	assert isinstance(kwargs, dict), "kwargs must be a dict (from **kwargs)"

	if not kwargs:
		return args

	return (args, _KWD_MARK, frozenset(kwargs.items()))


def request_cache(func: Callable) -> Callable:
	"""
	Decorator to cache function calls mid-request.

	Cache is stored in `frappe.local.request_cache`.

	The cache only persists for the current request and is cleared when the request is over.

	The function is called just once per request with the same set of (kw)arguments.

	---
	Usage:
	```
	        from frappe.utils.caching import request_cache

	        @request_cache
	        def calculate_pi(num_terms=0):
	            import math, time

	            print(f"{num_terms = }")
	            time.sleep(10)
	            return math.pi

	        calculate_pi(10)  # will calculate value
	        calculate_pi(10)  # will return value from cache
	```
	"""

	@wraps(func)
	def wrapper(*args, **kwargs):
		_cache = getattr(frappe.local, "request_cache", None)
		if _cache is None:
			return func(*args, **kwargs)
		try:
			args_key = __generate_request_cache_key(args, kwargs)
		except Exception:
			return func(*args, **kwargs)

		try:
			return _cache[func][args_key]
		except TypeError:
			# args_key is not hashable
			return func(*args, **kwargs)
		except KeyError:
			# cache miss
			return_val = func(*args, **kwargs)
			_cache[func][args_key] = return_val
			return return_val

	return wrapper


def site_cache(ttl: int | None = 3600, maxsize: int = 16) -> Callable:
	"""
	Decorator to cache method calls and its return values in Client_cache.
		# TODO: implement some policy to evict. Just set `maxsize` to be double or higher count for desired functions for now.
		# NOTE: `shared = False` is used as cache is supposed to be site-specific.
	args:
	        ttl: time to expiry in seconds, defaults to 1 hour
	        maxsize:int   to limit the number of count, a func can be called with different arguments.
	"""

	def wrapper(func: Callable | None = None) -> Callable:
		# Final key would be conditioned on function_name + args + site/database name.
		func_key = f"{func.__module__}.{func.__qualname__}"

		def clear_cache():
			if (
				frappe.client_cache
			):  # In case called during boot-straping itself, frappe.client_cache won't be available.
				frappe.client_cache.delete_keys(func_key)
				func.cached_values_counter = 0

		func.clear_cache = clear_cache
		func.ttl = ttl if not callable(ttl) else 3600
		func.maxsize = maxsize
		func.cached_values_counter = 0

		@wraps(func)
		def site_cache_wrapper(*args, **kwargs):
			# NOTE: reason for both checks is to support `site_cache` functionality too, but by default it would create
			# a `boot-strapping` problem, as internally `redis_wrapper` depends on `local.conf`. We also wait for `frappe.client_cache` to be available.
			if not (frappe.client_cache) or not (hasattr(frappe.local, "conf")):
				return func(*args, **kwargs)

			func_call_key = f"{func_key}::{hash(__generate_request_cache_key(args, kwargs))}"
			cached_val = frappe.client_cache.get_value(func_call_key, shared=False, ttl=func.ttl)
			if cached_val is not None:
				return cached_val

			val = func(*args, **kwargs)
			if (func.cached_values_counter + 1) > func.maxsize:
				return val

			if val is None:
				return None

			ttl = getattr(func, "ttl", 3600)
			frappe.client_cache.set_value(func_call_key, val, shared=False, ttl=ttl)
			# NOTE: since `client_cache` is technically a dictionary, so assumed we would always be successful in `set_value` call (given no error occured), we increment the following counter.
			func.cached_values_counter += 1
			return val

		return site_cache_wrapper

	if callable(ttl):
		return wrapper(ttl)
	return wrapper


def redis_cache(ttl: int | None = 3600, user: str | bool | None = None, shared: bool = False) -> Callable:
	"""Decorator to cache method calls and its return values in Redis

	args:
	        ttl: time to expiry in seconds, defaults to 1 hour
	        user: `true` should cache be specific to session user.
	        shared: `true` should cache be shared across sites
	"""

	def wrapper(func: Callable | None = None) -> Callable:
		func_key = f"{func.__module__}.{func.__qualname__}"

		def clear_cache():
			frappe.cache.delete_keys(func_key, user=user, shared=shared)

		func.clear_cache = clear_cache
		func.ttl = ttl if not callable(ttl) else 3600

		@wraps(func)
		def redis_cache_wrapper(*args, **kwargs):
			func_call_key = f"{func_key}::{hash(__generate_request_cache_key(args, kwargs))}"
			cached_val = frappe.cache.get_value(func_call_key, user=user, shared=shared)
			if cached_val is not None:
				return cached_val

			# Edge Case: None can mean two things: cache miss or the result itself is `None`
			# RedisWrapper doesn't give us any way to handle this cleanly.
			if frappe.cache.exists(func_call_key, user=user, shared=shared):
				return None

			val = func(*args, **kwargs)
			ttl = getattr(func, "ttl", 3600)
			frappe.cache.set_value(func_call_key, val, expires_in_sec=ttl, user=user, shared=shared)
			return val

		return redis_cache_wrapper

	if callable(ttl):
		return wrapper(ttl)
	return wrapper


def http_cache(
	*,
	public: bool = False,
	max_age: int | None = None,
	stale_while_revalidate: int | None = None,
) -> Callable:
	"""Decorator to send cache-control response from whitelisted endpoints.

	Reference: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control

	args:
		public: Results can be cached by proxy if set to True, otherwise only client (browser) can
				cache results.
		max_age: Cache Time-To-Live
		stale_while_revalidate: Duration for which stale response can be served while revalidation
								occurs.
	"""
	assert isinstance(stale_while_revalidate, int | NoneType)
	assert isinstance(max_age, int | NoneType)

	cache_headers = []
	if public:
		cache_headers.append("public")
	else:
		cache_headers.append("private")
	if max_age is not None:
		cache_headers.append(f"max-age={max_age}")
	if stale_while_revalidate is not None:
		cache_headers.append(f"stale-while-revalidate={stale_while_revalidate}")
	cache_headers = ",".join(cache_headers)

	def outer(func: Callable) -> Callable:
		qualified_name = f"{func.__module__}.{func.__name__}"

		@wraps(func)
		def inner(*args, **kwargs):
			ret = func(*args, **kwargs)
			if frappe.request and frappe.request.method == "GET" and qualified_name in frappe.request.path:
				frappe.local.response_headers.set("Cache-Control", cache_headers)
			return ret

		return inner

	return outer


def deprecated_local_cache(namespace, key, generator, regenerate_if_none=False):
	if namespace not in frappe.local.cache:
		frappe.local.cache[namespace] = {}

	if key not in frappe.local.cache[namespace]:
		frappe.local.cache[namespace][key] = generator()

	elif frappe.local.cache[namespace][key] is None and regenerate_if_none:
		# if key exists but the previous result was None
		frappe.local.cache[namespace][key] = generator()

	return frappe.local.cache[namespace][key]
