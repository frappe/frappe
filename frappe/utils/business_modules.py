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
from frappe.utils.caching import request_cache

HOOK_NAME = "business_modules"

_FIELDNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@request_cache
def get_business_modules() -> list[dict]:
	"""Return all modules registered by installed apps, in install order.

	Each item has: module, fieldname, app.
	Bad entries are skipped and logged. They never raise, so one bad hook cannot break login.
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
	"""Return only the module names."""
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
