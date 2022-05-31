# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. Check LICENSE

import json
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Dict, Optional, Tuple

import frappe

_SITE_CACHE = defaultdict(lambda: defaultdict(dict))


def __generate_request_cache_key(func: Callable, args: Tuple, kwargs: Dict):
	"""Generate a key for the cache."""
	return f"{func.__module__}.{func.__name__}{json.dumps((args, kwargs))}"


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
			frappe.local.request_cache = {}

		logger = frappe.logger(module=__name__)

		try:
			key = __generate_request_cache_key(func, args, kwargs)
		except Exception:
			logger.warning(f"request_cache: Couldn't generate key for args: {args}, kwargs: {kwargs}")
			return func(*args, **kwargs)

		if key not in frappe.local.request_cache:
			frappe.local.request_cache[key] = func(*args, **kwargs)
			logger.debug(f"request_cache: Cached key {key}")
		logger.debug(f"request_cache: Hit cache with key {key}")
		return frappe.local.request_cache[key]

	return wrapper


def site_cache(ttl: Optional[int] = None) -> Callable:
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
		nonlocal ttl

		func_key = f"{func.__module__}.{func.__name__}"

		def clear_cache():
			"""Clear cache for this function for all sites if not specified."""
			_SITE_CACHE[func_key].clear()

		func.clear_cache = clear_cache

		if ttl is not None and not callable(ttl):
			func.ttl = ttl
			func.expiration = datetime.utcnow() + timedelta(seconds=func.ttl)

		@wraps(func)
		def site_cache_wrapper(*args, **kwargs):
			if getattr(frappe.local, "initialised", None):
				func_call_key = json.dumps((args, kwargs))

				if hasattr(func, "ttl") and datetime.utcnow() >= func.expiration:
					func.clear_cache()
					func.expiration = datetime.utcnow() + +timedelta(seconds=func.ttl)

				if func_call_key not in _SITE_CACHE[func_key][frappe.local.site]:
					_SITE_CACHE[func_key][frappe.local.site][func_call_key] = func(*args, **kwargs)

				return _SITE_CACHE[func_key][frappe.local.site][func_call_key]

			return func(*args, **kwargs)

		return site_cache_wrapper

	if callable(ttl):
		return time_cache_wrapper(ttl)

	return time_cache_wrapper
