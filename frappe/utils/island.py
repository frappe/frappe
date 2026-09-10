# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Desk islands: the registry that turns an island's name into its bundle.

An app declares an island in `hooks.py`, against the bundle name its build
registers in assets.json:

    ui_islands = {"insights.dashboard": "insights_dashboard"}

A `Page` of type "Frappe UI" registers itself instead, so a desk route drawn
by an island needs no hook. Its name is `<app>.page.<page name>`, which the
build derives from the same page folder, and the `page` infix keeps it out of
the names an app declares by hand.

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

# Sits between the app and the page name, so a page island and a hand-declared
# island can never claim the same name.
PAGE_ISLAND_INFIX = "page"


def page_island_name(app: str, page: str) -> str:
	"""The one name a page island is known by, on both sides of the build."""
	return f"{app}.{PAGE_ISLAND_INFIX}.{page}"


def get_ui_islands() -> dict[str, str]:
	"""Island name -> bundle name, across every installed app."""
	islands = {}

	for name, value in frappe.get_hooks("ui_islands", default={}).items():
		# A dict hook collects one list of values per key. An island has exactly
		# one bundle, so the last app to declare the name wins.
		islands[name] = value[-1] if isinstance(value, list) else value

	islands.update(get_page_islands())

	return islands


def get_page_islands() -> dict[str, str]:
	"""Island name -> bundle name, for every Frappe UI page on the site.

	The name and the bundle are the same string. One name is enough because the
	`page` infix already keeps it clear of both registries it lives in: the
	island names an app declares, and the asset keys every app's island build
	writes into assets.json.

	A page whose module belongs to no installed app is skipped. It has no source
	folder to build from, so there is nothing to resolve.
	"""
	islands = {}

	for page in frappe.get_all("Page", filters={"type": "Frappe UI"}, fields=["name", "module"]):
		app = frappe.local.module_app.get(frappe.scrub(page.module))
		if app:
			name = page_island_name(app, page.name)
			islands[name] = name

	return islands


@frappe.whitelist()
def get_island_assets(name: str) -> dict:
	"""Island name -> `{"js": url, "css": url or None}`.

	For a host page that has no desk boot to resolve the name against.
	"""
	bundle = get_ui_islands().get(name)
	if not bundle:
		frappe.throw(
			_('Island "{0}" is not declared. Add it to ui_islands in the hooks.py of the app.').format(name)
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
