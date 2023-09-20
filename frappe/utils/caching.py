# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. Check LICENSE

import json
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable

import frappe

_SITE_CACHE = defaultdict(lambda: defaultdict(dict))


def __generate_request_cache_key(args: tuple, kwargs: dict):
	"""Generate a key for the cache."""
	if not kwargs:
		return hash(args)
	return hash((args, frozenset(kwargs.items())))


def request_cache(func: Callable) -> Callable:
	"""Decorator to cache function calls mid-request. Cache is stored in
	frappe.local.request_cache. The cache only persists for the current request
	and is cleared when the request is over. The function is called just once
	per request with the same set of (kw)arguments.

	Usage:
	        from frappe.utils.caching import request_cache

	        @request_cache
	        def calculate_pi(num_terms=0):
	                import math, time
	                print(f"{num_terms = }")
	                time.sleep(10)
	                return math.pi

	        calculate_pi(10) # will calculate value
	        calculate_pi(10) # will return value from cache
	"""

	@wraps(func)
	def wrapper(*args, **kwargs):
		if not getattr(frappe.local, "initialised", None):
			return func(*args, **kwargs)
		if not hasattr(frappe.local, "request_cache"):
			frappe.local.request_cache = defaultdict(dict)

		try:
			args_key = __generate_request_cache_key(args, kwargs)
		except Exception:
			return func(*args, **kwargs)

		try:
			return frappe.local.request_cache[func][args_key]
		except KeyError:
			return_val = func(*args, **kwargs)
			frappe.local.request_cache[func][args_key] = return_val
			return return_val

	return wrapper


def site_cache(ttl: int | None = None, maxsize: int | None = None) -> Callable:
	"""Decorator to cache method calls across requests. The cache is stored in
	frappe.utils.caching._SITE_CACHE. The cache persists on the parent process.
	It offers a light-weight cache for the current process without the additional
	overhead of serializing / deserializing Python objects.

	Note: This cache isn't shared among workers. If you need to share data across
	workers, use redis (frappe.cache API) instead.

	Usage:
	        from frappe.utils.caching import site_cache

	        @site_cache
	        def calculate_pi():
	                import math, time
	                precision = get_precision("Math Constant", "Pi") # depends on site data
	                return round(math.pi, precision)

	        calculate_pi(10) # will calculate value
	        calculate_pi(10) # will return value from cache
	        calculate_pi.clear_cache() # clear this function's cache for all sites
	        calculate_pi(10) # will calculate value
	"""

	def time_cache_wrapper(func: Callable = None) -> Callable:
		func_key = f"{func.__module__}.{func.__name__}"

		def clear_cache():
			"""Clear cache for this function for all sites if not specified."""
			_SITE_CACHE[func_key].clear()

		func.clear_cache = clear_cache

		if ttl is not None and not callable(ttl):
			func.ttl = ttl
			func.expiration = datetime.utcnow() + timedelta(seconds=func.ttl)

		if maxsize is not None and not callable(maxsize):
			func.maxsize = maxsize

		@wraps(func)
		def site_cache_wrapper(*args, **kwargs):
			if getattr(frappe.local, "initialised", None):
				func_call_key = json.dumps((args, kwargs))

				if hasattr(func, "ttl") and datetime.utcnow() >= func.expiration:
					func.clear_cache()
					func.expiration = datetime.utcnow() + timedelta(seconds=func.ttl)

				if hasattr(func, "maxsize") and len(_SITE_CACHE[func_key][frappe.local.site]) >= func.maxsize:
					_SITE_CACHE[func_key][frappe.local.site].pop(
						next(iter(_SITE_CACHE[func_key][frappe.local.site])), None
					)

				if func_call_key not in _SITE_CACHE[func_key][frappe.local.site]:
					_SITE_CACHE[func_key][frappe.local.site][func_call_key] = func(*args, **kwargs)

				return _SITE_CACHE[func_key][frappe.local.site][func_call_key]

			return func(*args, **kwargs)

		return site_cache_wrapper

	if callable(ttl):
		return time_cache_wrapper(ttl)

	return time_cache_wrapper


def redis_cache(ttl: int | None = 3600, user: str | bool | None = None) -> Callable:
	"""Decorator to cache method calls and its return values in Redis

	args:
	        ttl: time to expiry in seconds, defaults to 1 hour
	        user: `true` should cache be specific to session user.
	"""

	def wrapper(func: Callable = None) -> Callable:

		func_key = f"{func.__module__}.{func.__qualname__}"

		def clear_cache():
			frappe.cache().delete_keys(func_key)

		func.clear_cache = clear_cache
		func.ttl = ttl if not callable(ttl) else 3600

		@wraps(func)
		def redis_cache_wrapper(*args, **kwargs):
			func_call_key = func_key + str(__generate_request_cache_key(args, kwargs))
			if frappe.cache().exists(func_call_key):
				return frappe.cache().get_value(func_call_key, user=user)
			else:
				val = func(*args, **kwargs)
				ttl = getattr(func, "ttl", 3600)
				frappe.cache().set_value(func_call_key, val, expires_in_sec=ttl, user=user)
				return val

		return redis_cache_wrapper

	if callable(ttl):
		return wrapper(ttl)
	return wrapper
