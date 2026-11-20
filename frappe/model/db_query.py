# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Removed legacy list query engine.

`frappe.get_list` / `frappe.get_all` run on `frappe.model.qb_query.DatabaseQuery`.
The helpers that used to live here are re-exported from their new modules until v17.
"""

import importlib

import frappe
from frappe.deprecation_dumpster import deprecation_warning

_MOVED = {
	"get_order_by": "frappe.model.qb_query",
	"get_between_date_filter": "frappe.database.query",
	"get_additional_filter_field": "frappe.database.query",
	"get_date_range": "frappe.database.query",
	"requires_owner_constraint": "frappe.permissions",
	"get_timespan_date_range": "frappe.utils",
}


def __getattr__(name: str):
	if name == "DatabaseQuery":
		raise AttributeError(
			"frappe.model.db_query.DatabaseQuery was removed. "
			"Use frappe.get_list / frappe.get_all, or frappe.model.qb_query.DatabaseQuery."
		)

	if module := _MOVED.get(name):
		deprecation_warning(
			"2026-11-20",
			"v17",
			f"Import {name} from {module} instead of frappe.model.db_query.",
		)
		return getattr(importlib.import_module(module), name)

	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
