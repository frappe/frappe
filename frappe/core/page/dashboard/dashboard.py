# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import json
import frappe
from frappe.utils import add_to_date


def cache_source(function):
	def wrapper(*args, **kwargs):
		chart = kwargs.get("chart")
		no_cache = kwargs.get("no_cache")
		if no_cache:
			return function(chart, no_cache)
		chart_name = frappe.parse_json(chart).name
		cache_key = "chart-data:{}".format(chart_name)
		if int(kwargs.get("refresh") or 0):
			results = generate_and_cache_results(chart, chart_name, function, cache_key)
		else:
			cached_results = frappe.cache().get_value(cache_key)
			if cached_results:
				results = frappe.parse_json(frappe.safe_decode(cached_results))
			else:
				results = generate_and_cache_results(chart, chart_name, function, cache_key)
		return results
	return wrapper

def generate_and_cache_results(chart, chart_name, function, cache_key):
	results = function(chart)
	frappe.cache().set_value(cache_key, json.dumps(results, default=str))
	frappe.db.set_value("Dashboard Chart", chart_name, "last_synced_on", frappe.utils.now(), update_modified = False)
	return results

def get_from_date_from_timespan(to_date, timespan):
	days = months = years = 0
	if "Last Week" == timespan:
		days = -7
	if "Last Month" == timespan:
		months = -1
	elif "Last Quarter" == timespan:
		months = -3
	elif "Last Year" == timespan:
		years = -1
	return add_to_date(to_date, years=years, months=months, days=days,
		as_datetime=True)
