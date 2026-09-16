# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.query_builder.functions import IfNull


def is_disabled_app_filtering_active() -> bool:
	"""Return False during maintenance, so a disabled app is never hidden mid-operation."""
	return not (
		frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_patch
		or frappe.flags.in_import
		or frappe.flags.in_uninstall
		or frappe.flags.in_setup_wizard
		or frappe.flags.in_app_toggle
	)


def clear_cache_after_maintenance():
	"""Drop the caches that a maintenance operation filled.

	While a maintenance flag is set, Frappe caches meta and hooks that still hold the
	customizations of a disabled app. A site with no disabled app has nothing to drop.
	"""
	if frappe.get_disabled_apps():
		frappe.clear_cache()


@frappe.request_cache
def get_disabled_modules() -> set[str]:
	"""Return `Module Def` names owned by apps that are disabled on this site.

	Derived per request rather than cached across them, so it can never contradict the
	`disabled_apps` global a worker is currently reading.
	"""
	if not is_disabled_app_filtering_active():
		return set()

	disabled_apps = frappe.get_disabled_apps()
	if not disabled_apps:
		return set()

	module_def = frappe.qb.DocType("Module Def")
	return set(
		frappe.qb.from_(module_def)
		.select(module_def.name)
		# `custom = 0`: a site's own module is only placed in an app, so turning that app off
		# takes the app's modules with it and never the site's. Same split as the uninstall filter
		# in `frappe.installer.get_app_owned_modules`.
		.where(module_def.app_name.isin(disabled_apps) & (module_def.custom == 0))
		.run(pluck=True)
	)


@frappe.request_cache
def get_disabled_doctypes() -> set[str]:
	"""Return DocTypes owned by apps that are disabled on this site."""
	disabled_modules = get_disabled_modules()
	if not disabled_modules:
		return set()

	doctype = frappe.qb.DocType("DocType")
	return set(
		frappe.qb.from_(doctype)
		.select(doctype.name)
		.where(doctype.module.isin(list(disabled_modules)))
		.run(pluck=True)
	)


def is_module_disabled(module: str) -> bool:
	return bool(module) and module in get_disabled_modules()


def filter_out_disabled_doctypes(doctypes: list[str]) -> list[str]:
	"""Drop DocTypes owned by an app that is disabled on this site."""
	disabled_doctypes = get_disabled_doctypes()
	if not disabled_doctypes:
		return doctypes

	return [doctype for doctype in doctypes if doctype not in disabled_doctypes]


def get_module_permission_query_conditions(user, doctype=None):
	"""Hide records of a disabled app from list views, for any DocType with a `module` field."""
	disabled_modules = get_disabled_modules()
	if not disabled_modules:
		return None

	return IfNull(frappe.qb.DocType(doctype).module, "").notin(list(disabled_modules))


def get_app_permission_query_conditions(user, doctype=None):
	"""Same as above, for DocTypes that name their owner in an `app` field instead."""
	disabled_apps = frappe.get_disabled_apps()
	if not disabled_apps:
		return None

	return IfNull(frappe.qb.DocType(doctype).app, "").notin(disabled_apps)
