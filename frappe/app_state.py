# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def is_concealment_active() -> bool:
	"""Return False during maintenance, so a disabled app is never hidden mid-operation."""
	return not (
		frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_patch
		or frappe.flags.in_import
		or frappe.flags.in_uninstall
		or frappe.flags.in_setup_wizard
	)


@frappe.request_cache
def get_disabled_modules() -> set[str]:
	"""Return `Module Def` names owned by apps that are disabled on this site.

	Derived per request rather than cached across them, so it can never contradict the
	`disabled_apps` global a worker is currently reading.
	"""
	if not is_concealment_active():
		return set()

	disabled_apps = frappe.get_disabled_apps()
	if not disabled_apps:
		return set()

	module_def = frappe.qb.DocType("Module Def")
	return set(
		frappe.qb.from_(module_def)
		.select(module_def.name)
		.where(module_def.app_name.isin(disabled_apps))
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
		return ""

	modules = ", ".join(frappe.db.escape(module) for module in disabled_modules)
	return f"`tab{doctype}`.`module` not in ({modules})"


def get_app_permission_query_conditions(user, doctype=None):
	"""Same as above, for DocTypes that name their owner in an `app` field instead."""
	disabled_apps = frappe.get_disabled_apps()
	if not disabled_apps:
		return ""

	apps = ", ".join(frappe.db.escape(app) for app in disabled_apps)
	return f"ifnull(`tab{doctype}`.`app`, '') not in ({apps})"
