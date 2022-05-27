# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. Check LICENSE

import json
from functools import wraps

import frappe


def __generate_key(func, args, kwargs):
	"""Generate a key for the cache."""
	return f"{func.__module__}.{func.__name__}{json.dumps((args, kwargs))}"


def request_cache(func):
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
			key = __generate_key(func, args, kwargs)
		except Exception:
			logger.warning(f"request_cache: Couldn't generate key for args: {args}, kwargs: {kwargs}")
			return func(*args, **kwargs)

		if key not in frappe.local.request_cache:
			frappe.local.request_cache[key] = func(*args, **kwargs)
			logger.debug(f"request_cache: Cached key {key}")
		logger.debug(f"request_cache: Hit cache with key {key}")
		return frappe.local.request_cache[key]

	return wrapper
