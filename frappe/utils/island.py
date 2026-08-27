# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Desk islands: the registry that turns an island's name into its bundle.

An app declares an island in `hooks.py`, against the bundle base name its build
registers in assets.json:

    ui_islands = {"insights.dashboard": "insights_dashboard"}

Boot carries the registry, and `frappe.ui.mount_island` resolves a name through
it. The `.island.js` and `.island.css` key forms differ from the legacy
`.bundle.js` one, so the module loader and the classic loader never claim the
same asset.
"""

import frappe

ISLAND_JS_SUFFIX = ".island.js"
ISLAND_CSS_SUFFIX = ".island.css"


def get_ui_islands() -> dict[str, str]:
	"""Island name -> bundle base name, across every installed app."""
	islands = {}

	for name, value in frappe.get_hooks("ui_islands", default={}).items():
		# A dict hook collects one list of values per key. An island has exactly
		# one bundle, so the last app to declare the name wins.
		islands[name] = value[-1] if isinstance(value, list) else value

	return islands
