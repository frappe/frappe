# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Desk islands: the registry that turns an island's name into its bundle.

An app declares an island in `hooks.py`, against the bundle name its build
registers in assets.json:

    ui_islands = {"insights.dashboard": "insights_dashboard"}

Two hosts resolve a name against the registry. The desk loader,
`frappe.ui.mount_island`, reads it from boot on the client. A page without desk
boot calls `get_island_assets`, which does the same lookup on the server.

The `.island.js` and `.island.css` key forms differ from the legacy `.bundle.js`
one, so the module loader and the classic loader never claim the same asset.
"""

import frappe
from frappe import _
from frappe.utils import get_assets_json

ISLAND_JS_SUFFIX = ".island.js"
ISLAND_CSS_SUFFIX = ".island.css"


def get_ui_islands() -> dict[str, str]:
	"""Island name -> bundle name, across every installed app."""
	islands = {}

	for name, value in frappe.get_hooks("ui_islands", default={}).items():
		# A dict hook collects one list of values per key. An island has exactly
		# one bundle, so the last app to declare the name wins.
		islands[name] = value[-1] if isinstance(value, list) else value

	return islands


@frappe.whitelist()
def get_island_assets(name: str) -> dict:
	"""Island name -> `{"js": url, "css": url or None}`.

	For a host page that has no desk boot to resolve the name against.
	"""
	bundle = get_ui_islands().get(name)
	if not bundle:
		frappe.throw(
			_('Island "{0}" is not declared. Add it to ui_islands in the app\'s hooks.py.').format(name)
		)

	assets_json = get_assets_json()
	js = assets_json.get(bundle + ISLAND_JS_SUFFIX)
	if not js:
		frappe.throw(
			_(
				'Island "{0}" points at bundle "{1}", but "{2}" is not in assets.json. Build the app that ships it.'
			).format(name, bundle, bundle + ISLAND_JS_SUFFIX)
		)

	return {"js": js, "css": assets_json.get(bundle + ISLAND_CSS_SUFFIX) or None}
