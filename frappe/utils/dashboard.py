# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import frappe
from frappe import _
from functools import wraps
from frappe.utils import add_to_date, cint, get_link_to_form
from frappe.modules.import_file import import_doc
import os
from os.path import join
import ast


def cache_source(function):
	@wraps(function)
	def wrapper(*args, **kwargs):
		if kwargs.get("chart_name"):
			chart = frappe.get_doc('Dashboard Chart', kwargs.get("chart_name"))
		else:
			chart = kwargs.get("chart")
		no_cache = kwargs.get("no_cache")
		if no_cache:
			return function(chart = chart, no_cache = no_cache)
		chart_name = frappe.parse_json(chart).name
		cache_key = "chart-data:{}".format(chart_name)
		if int(kwargs.get("refresh") or 0):
			results = generate_and_cache_results(kwargs, function, cache_key, chart)
		else:
			cached_results = frappe.cache().get_value(cache_key)
			if cached_results:
				results = frappe.parse_json(frappe.safe_decode(cached_results))
			else:
				results = generate_and_cache_results(kwargs, function, cache_key, chart)
		return results
	return wrapper

def generate_and_cache_results(args, function, cache_key, chart):
	try:
		args = frappe._dict(args)
		results = function(
			chart_name = args.chart_name,
			filters = args.filters or None,
			from_date = args.from_date or None,
			to_date = args.to_date or None,
			time_interval = args.time_interval or None,
			timespan = args.timespan or None,
			heatmap_year = args.heatmap_year or None
		)
	except TypeError as e:
		if str(e) == "'NoneType' object is not iterable":
			# Probably because of invalid link filter
			#
			# Note: Do not try to find the right way of doing this because
			# it results in an inelegant & inefficient solution
			# ref: https://github.com/frappe/frappe/pull/9403
			frappe.throw(_('Please check the filter values set for Dashboard Chart: {}').format(
				get_link_to_form(chart.doctype, chart.name)), title=_('Invalid Filter Value'))
			return
		else:
			raise

	frappe.db.set_value("Dashboard Chart", args.chart_name, "last_synced_on", frappe.utils.now(), update_modified = False)
	return results

def get_from_date_from_timespan(to_date, timespan):
	days = months = years = 0
	if timespan == "Last Week":
		days = -7
	if timespan == "Last Month":
		months = -1
	elif timespan == "Last Quarter":
		months = -3
	elif timespan == "Last Year":
		years = -1
	elif timespan == "All Time":
		years = -50
	return add_to_date(to_date, years=years, months=months, days=days,
		as_datetime=True)

def create_filters_file_after_export(module_name, dashboard_name):
	dashboard_path = frappe.get_module_path(\
		module_name,\
		"{module_name}_dashboard".format(module_name=module_name),\
		"{dashboard}".format(dashboard=dashboard_name)\
	)
	charts_path = frappe.get_module_path(module_name, "dashboard charts")
	create_filters_file(charts_path, dashboard_path, 'dashboard_chart_filters')
	cards_path = frappe.get_module_path(module_name, "number cards")
	create_filters_file(cards_path, dashboard_path, 'number_card_filters')


def sync_dashboards(app=None):
	"""Import, overwrite fixtures from `[app]/fixtures`"""
	if not cint(frappe.db.get_single_value('System Settings', 'setup_complete')):
		return
	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()

	for app_name in apps:
		print("Updating Dashboard for {app}".format(app=app_name))
		for module_name in frappe.local.app_modules.get(app_name) or []:
			frappe.flags.in_import = True
			make_records_in_module(app_name, module_name)
			frappe.flags.in_import = False

def make_records_in_module(app, module):
	dashboards_path = frappe.get_module_path(module, "{module}_dashboard".format(module=module))
	if os.path.isdir(dashboards_path):
		for fname in os.listdir(dashboards_path):
			dashboard_path = dashboards_path + '/{}'.format(fname)
			if os.path.isdir(dashboard_path):
				if fname == '__pycache__':
					continue

				# create records for all dashboards in the module
				make_records(dashboards_path)

		charts_path = frappe.get_module_path(module, "dashboard chart")
		cards_path = frappe.get_module_path(module, "number card")
		make_records(charts_path)
		make_records(cards_path)

def make_records(path, filters=None):
	for fname in os.listdir(path):
		if os.path.isdir(join(path, fname)):
			if fname == '__pycache__':
				continue
			try:
				doc_dict = frappe.get_file_json("{path}/{fname}/{fname}.json".format(path=path, fname=fname))
				import_doc(doc_dict)
			except FileNotFoundError:
				frappe.log_error(message=frappe.get_traceback(), title="Dashboard Sync")
				pass
