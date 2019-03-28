# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import json
import frappe


def cache_source(function):
	def wrapper(*args, **kwargs):
		filters = json.loads(kwargs.get("filters", "{}"))
		chart_name = kwargs.get("chart_name")
		cache_key = json.dumps({
			"name": chart_name,
			"filters": filters
		}, default=str)
		if kwargs.get("refresh"):
			results = generate_and_cache_results(chart_name, function, filters, cache_key)
		else:
			cached_results = frappe.cache().get_value(cache_key)
			if cached_results:
				results = json.loads(frappe.safe_decode(cached_results))
			else:
				results = generate_and_cache_results(chart_name, function, filters, cache_key)
		return results
	return wrapper


def generate_and_cache_results(chart_name, function, filters, cache_key):
	results = function(frappe._dict(filters))
	frappe.cache().set_value(cache_key, json.dumps(results, default=str))
	frappe.db.set_value("Dashboard Chart", chart_name, "last_synced_on", frappe.utils.now())
	return results
