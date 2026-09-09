# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Desk islands: the registry that says which islands a site has.

An island is registered by being built. Its name is the asset key its build
writes into assets.json, without the `.island.js` suffix:

    insights.dashboard.island.js  ->  insights.dashboard

assets.json is bench-wide, so the registry keeps only the islands of the apps
installed on the site. An island's app is the one its URL is served from,
`/assets/<app>/dist/...`, except for a page island, which framework builds into
its own dist and which carries its app in its name, `<app>.page.<page name>`.

Two hosts resolve a name against the registry. The desk loader,
`frappe.ui.mount_island`, reads it from boot on the client. A page without desk
boot calls `get_island_assets`, which does the same lookup on the server.

The `.island.js` and `.island.css` key forms differ from the legacy `.bundle.js`
one, so the module loader and the classic loader never claim the same asset.
"""

import re

import frappe
from frappe import _
from frappe.utils import get_assets_json

ISLAND_JS_SUFFIX = ".island.js"
ISLAND_CSS_SUFFIX = ".island.css"

# Sits between the app and the page name, so a page island and an island an app
# builds itself can never claim the same name.
PAGE_ISLAND_INFIX = "page"

ASSET_APP = re.compile(r"^/assets/([^/]+)/")


def page_island_name(app: str, page: str) -> str:
	"""The one name a page island is known by, on both sides of the build."""
	return f"{app}.{PAGE_ISLAND_INFIX}.{page}"


def get_ui_islands() -> list[str]:
	"""Every island on this site, by name."""
	installed = set(frappe.get_installed_apps())

	return sorted(
		name
		for key, url in get_assets_json().items()
		if (name := island_name(key)) and island_app(name, url) in installed
	)


def island_name(asset_key: str) -> str | None:
	"""The island an asset key registers, or `None` for any other key."""
	if asset_key.endswith(ISLAND_JS_SUFFIX):
		return asset_key.removesuffix(ISLAND_JS_SUFFIX)


def island_app(name: str, url: str) -> str | None:
	"""The app an island belongs to, which is what decides it is on this site.

	Framework builds every page island, into framework's own dist, so a page
	island's URL names framework and its name names the app whose page it draws.
	"""
	app, infix, _page = name.partition(f".{PAGE_ISLAND_INFIX}.")
	if infix:
		return app

	if match := ASSET_APP.match(url):
		return match.group(1)


@frappe.whitelist()
def get_island_assets(name: str) -> dict:
	"""Island name -> `{"js": url, "css": url or None}`.

	For a host page that has no desk boot to resolve the name against.
	"""
	assets_json = get_assets_json()
	js = assets_json.get(name + ISLAND_JS_SUFFIX) if name in get_ui_islands() else None
	if not js:
		frappe.throw(_('Island "{0}" is not on this site. Build the app that ships it.').format(name))

	return {"js": js, "css": assets_json.get(name + ISLAND_CSS_SUFFIX) or None}
