# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
from functools import wraps
from os.path import join

import frappe
from frappe import _
from frappe.modules.import_file import import_file_by_path
from frappe.utils import cint, get_link_to_form


def cache_source(function):

    @wraps(function)
    def wrapper(*args, **kwargs):
        if kwargs.get("chart_name"):
            chart = frappe.get_doc("Dashboard Chart", kwargs.get("chart_name"))
        else:
            chart = kwargs.get("chart")
        no_cache = kwargs.get("no_cache")
        if no_cache:
            return function(chart=chart, no_cache=no_cache)
        chart_name = frappe.parse_json(chart).name
        cache_key = f"chart-data:{chart_name}"
        if int(kwargs.get("refresh") or 0):
            results = generate_and_cache_results(kwargs, function, cache_key, chart)
        else:
            cached_results = frappe.cache.get_value(cache_key)
            if cached_results:
                results = frappe.parse_json(frappe.safe_decode(cached_results))
            else:
                results = generate_and_cache_results(kwargs, function, cache_key, chart)
        return results

    return wrapper


def generate_and_cache_results(args, function, cache_key, chart):
    """
    Generate and cache the results of a function call.

    This function takes in several arguments: args, function, cache_key, and chart.
    It tries
    to execute the given function with the specified arguments and stores the
    result in a variable called results. If an exception of type TypeError is
    raised, the code checks if the error message is 'NoneType' object is not
    iterable. If it is, the code throws a frappe exception with a specific
    error message and returns. If the error message is different, the
    exception is re-raised. Finally, if frappe flags are not set to read_only,
    the code updates the 'last_synced_on' field of a 'Dashboard Chart'
    document in the frappe database. The function then returns the results
    variable.
    """
    try:
        args = frappe._dict(args)
        results = function(
        	chart_name=args.chart_name,
        	filters=args.filters or None,
        	from_date=args.from_date or None,
        	to_date=args.to_date or None,
        	time_interval=args.time_interval or None,
        	timespan=args.timespan or None,
        	heatmap_year=args.heatmap_year or None,
        )
    except TypeError as e:
        if str(e) == "'NoneType' object is not iterable":
            # Probably because of invalid link filter
            #
            # Note: Do not try to find the right way of doing this because
            # it results in an inelegant & inefficient solution
            # ref: https://github.com/frappe/frappe/pull/9403
            frappe.throw(
            	_("Please check the filter values set for Dashboard Chart: {}").format(
            		get_link_to_form(chart.doctype, chart.name)
            	),
            	title=_("Invalid Filter Value"),
            )
            return
        else:
            raise

    if not frappe.flags.read_only:
        frappe.db.set_value(
        	"Dashboard Chart", args.chart_name, "last_synced_on", frappe.utils.now(), update_modified=False
        )
    return results


def get_dashboards_with_link(docname, doctype):
    """Get dashboards with link."""
    dashboards = []
    links = []

    if doctype == "Dashboard Chart":
        links = frappe.get_all("Dashboard Chart Link", fields=["parent"], filters={"chart": docname})
    elif doctype == "Number Card":
        links = frappe.get_all("Number Card Link", fields=["parent"], filters={"card": docname})

    return [link.parent for link in links]


def sync_dashboards(app=None):
    """Import, overwrite dashboards from `[app]/[app]_dashboard`"""
    apps = [app] if app else frappe.get_installed_apps()

    for app_name in apps:
        print(f"Updating Dashboard for {app_name}")
        for module_name in frappe.local.app_modules.get(app_name) or []:
            frappe.flags.in_import = True
            make_records_in_module(app_name, module_name)
            frappe.flags.in_import = False


def make_records_in_module(app, module):
    """Make records in module."""
    dashboards_path = frappe.get_module_path(module, f"{module}_dashboard")
    charts_path = frappe.get_module_path(module, "dashboard chart")
    cards_path = frappe.get_module_path(module, "number card")

    paths = [dashboards_path, charts_path, cards_path]
    for path in paths:
        make_records(path)


def make_records(path, filters=None):
    """
    Create records from files in the given path.

    This function takes in a 'path' argument representing a directory and an
    optional 'filters' argument.
    If the 'path' is a directory, the function iterates over the files in the directory.
    If a file is itself a directory and not the '__pycache__' directory, it imports
    the file using the 'import_file_by_path' function.

    Args:
        path (str): The path to the directory.
        filters (optional): A list of filters to apply (default is None).

    Returns:
        None
    """
    if os.path.isdir(path):
        for fname in os.listdir(path):
            if os.path.isdir(join(path, fname)):
                if fname == "__pycache__":
                    continue
                import_file_by_path("{path}/{fname}/{fname}.json".format(path=path, fname=fname))
