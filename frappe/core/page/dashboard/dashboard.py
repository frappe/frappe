# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import json
import os
import frappe
from frappe.modules import get_module_path
from frappe.model.utils import render_include


@frappe.whitelist()
def get_data(chart_name, refresh=False):
	chart = frappe.get_doc("Dashboard Chart", chart_name)
	filters = json.loads(chart.filters_json)
	cache_key = json.dumps({
		"name": chart.method_path,
		"filters": filters
	}, default=str)

	if refresh == "true":
		results = generate_and_cache_results(chart, filters, cache_key)
	else:
		cached_results = frappe.cache().get_value(cache_key)
		if cached_results:
			results = json.loads(frappe.safe_decode(cached_results))
		else:
			results = generate_and_cache_results(chart, filters, cache_key)
	return results


def generate_and_cache_results(chart, filters, cache_key):
	results = frappe.get_attr(chart.method_path)(filters=frappe._dict(filters))
	frappe.cache().set_value(cache_key, json.dumps(results, default=str))
	frappe.db.set_value("Dashboard Chart", chart.name, "last_synced_on", frappe.utils.now())
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
