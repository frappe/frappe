# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import json
import os
import frappe
from frappe.modules import get_module_path
from frappe.model.utils import render_include


def cache_source(function):
	def wrapper(*args, **kwargs):
		filters = json.loads(kwargs.get("filters", "{}"))
		chart_name = kwargs.get("chart_name")
		cache_key = json.dumps({
			"name": chart_name,
			"filters": filters
		}, default=str)
		if kwargs.get("refresh") == "true":
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


@frappe.whitelist()
def get_script(source_name):
	source = frappe.get_doc("Dashboard Chart Source", source_name)
	module_path = get_module_path(source.module)
	scrubbed_source_name = frappe.scrub(source_name)
	script_path = os.path.join(module_path, "dashboard_chart_source", scrubbed_source_name, scrubbed_source_name + ".js")

	if os.path.exists(script_path):
		with open(script_path, "r") as f:
			script = f.read()

	return {
		"script": render_include(script),
	}
