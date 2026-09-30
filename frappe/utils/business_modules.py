# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Business modules registered by apps through the ``business_modules`` hook.

A business module is a part of an app that can be switched on or off, such as
Stock or Point of Sale. Fields, sidebars, dashboards, reports and more can adapt
to which modules are on.

Frappe only collects the list. The app that registers the modules decides where
the switches live and what reacts to them.

Apps declare their modules in ``hooks.py``::

    business_modules = [
        {"module": "Stock", "fieldname": "stock"},
        {"module": "Manufacturing", "fieldname": "manufacturing"},
    ]

``module``
    The name. Use the same name as the app's Module Def when one exists, for
    example "Stock" or "Manufacturing". If no Module Def fits, pick a clear name,
    for example "POS". The name is saved wherever the module is used, so do not
    rename it later.
``fieldname``
    The Check field that turns the module on or off. ERPNext puts it on Company.

If two apps register the same name, the first installed app wins.
"""

import re

import frappe
from frappe import _
from frappe.utils.caching import request_cache

HOOK_NAME = "business_modules"

_FIELDNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@request_cache
def get_business_modules() -> list[dict]:
	"""Return all modules registered by installed apps, in install order.

	Each item has: module, fieldname, app. Bad entries are skipped and logged.

	Example: get_business_modules() -> [{"module": "Stock", "fieldname": "stock", "app": "erpnext"}]
	"""
	modules: list[dict] = []
	seen: set[str] = set()

	for app in frappe.get_installed_apps():
		for entry in frappe.get_hooks(HOOK_NAME, app_name=app) or []:
			module = _validate_entry(entry, app)
			if not module or module["module"] in seen:
				continue
			seen.add(module["module"])
			modules.append(module)

	return modules


def get_business_module_names() -> list[str]:
	"""Return only the module names. Example: ["Stock", "POS"]"""
	return [m["module"] for m in get_business_modules()]


def _validate_entry(entry, app: str) -> dict | None:
	"""Check one hook entry. Return a clean copy, or None if it is bad."""
	if not isinstance(entry, dict):
		_log_invalid(app, entry, "entry must be a dict")
		return None

	module = entry.get("module")
	fieldname = entry.get("fieldname")

	if not isinstance(module, str) or not module.strip():
		_log_invalid(app, entry, "'module' must be a non-empty string")
		return None
	if not isinstance(fieldname, str) or not _FIELDNAME_PATTERN.match(fieldname):
		_log_invalid(app, entry, "'fieldname' must be a valid fieldname (lowercase, letters, digits, _)")
		return None

	return {
		"module": module.strip(),
		"fieldname": fieldname,
		"app": app,
	}


def _log_invalid(app: str, entry, reason: str) -> None:
	frappe.logger("business_modules").warning(
		f"Ignoring invalid {HOOK_NAME} entry in app '{app}': {reason}. Entry: {entry!r}"
	)


def validate_show_for_module(field, doctype: str | None = None) -> None:
	"""Check the Show for Module value of one field. Call it on save.

	Rule 1: a mandatory field cannot have a module. The value is cleared, with a message.
	Rule 2: the module must be registered. Skipped during install and migrate.

	"""
	module = field.get("show_for_module")
	if not module:
		return

	label = field.get("label") or field.get("fieldname")
	where = f"{doctype}: {label}" if doctype else label

	if field.get("reqd") or field.get("mandatory_depends_on"):
		field.set("show_for_module", None)
		if not (frappe.flags.in_install or frappe.flags.in_migrate):
			frappe.msgprint(
				_("Show for Module was cleared on {0} because the field is mandatory.").format(
					frappe.bold(where)
				),
				alert=True,
			)
		return

	if frappe.flags.in_install or frappe.flags.in_migrate:
		return

	if module not in get_business_module_names():
		frappe.throw(
			_("{0} is not a registered business module (field {1}).").format(frappe.bold(module), where)
		)
