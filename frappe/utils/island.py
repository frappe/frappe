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
import shutil

import frappe
from frappe import _
from frappe.utils import get_assets_json, get_files_path
from frappe.utils.synchronization import filelock

ISLAND_JS_SUFFIX = ".island.js"
ISLAND_CSS_SUFFIX = ".island.css"

# Sits between the app and the page name, so a page island and an island an app
# builds itself can never claim the same name.
PAGE_ISLAND_INFIX = "page"

ASSET_APP = re.compile(r"^/assets/([^/]+)/")

# A site builds its own islands into its public files, named `site.<name>`. No
# app can be called `site`, so a site island never takes an app island's name.
SITE_ISLAND_PREFIX = "site."
SITE_ISLANDS_FOLDER = "islands"
SITE_ISLANDS_MANIFEST = "islands.json"
SITE_ISLANDS_CACHE_KEY = "site_island_assets"


def page_island_name(app: str, page: str) -> str:
	"""The one name a page island is known by, on both sides of the build."""
	return f"{app}.{PAGE_ISLAND_INFIX}.{page}"


def get_ui_islands() -> list[str]:
	"""Every island on this site, by name."""
	installed = set(frappe.get_installed_apps())
	app_islands = {
		name
		for key, url in get_assets_json().items()
		if (name := island_name(key)) and island_app(name, url) in installed
	}
	site_islands = {name for key in get_site_island_assets() if (name := island_name(key))}

	return sorted(app_islands | site_islands)


def get_island_assets_json() -> dict[str, str]:
	"""assets.json with this site's own island keys added."""
	return {**get_assets_json(), **get_site_island_assets()}


def get_site_island_assets() -> dict[str, str]:
	"""Asset key -> URL for the islands this site built into its public files."""
	return frappe.client_cache.get_value(SITE_ISLANDS_CACHE_KEY, generator=read_site_island_manifest)


def read_site_island_manifest() -> dict[str, str]:
	return frappe.parse_json(frappe.read_file(get_site_islands_path(SITE_ISLANDS_MANIFEST))) or {}


def get_site_islands_path(*path: str) -> str:
	return get_files_path(SITE_ISLANDS_FOLDER, *path)


def set_site_island_assets(name: str, js: str, css: str | None) -> None:
	"""Register a site island, or replace the assets of one already registered."""
	with filelock(SITE_ISLANDS_CACHE_KEY):
		assets = get_manifest_without(name)
		assets[name + ISLAND_JS_SUFFIX] = js
		if css:
			assets[name + ISLAND_CSS_SUFFIX] = css
		write_site_island_manifest(assets)


def remove_site_island(name: str, folder: str) -> None:
	"""Unregister a site island and delete the folder its build wrote."""
	with filelock(SITE_ISLANDS_CACHE_KEY):
		write_site_island_manifest(get_manifest_without(name))
	shutil.rmtree(get_site_islands_path(folder), ignore_errors=True)


def get_manifest_without(name: str) -> dict[str, str]:
	own_keys = {name + ISLAND_JS_SUFFIX, name + ISLAND_CSS_SUFFIX}
	return {key: url for key, url in read_site_island_manifest().items() if key not in own_keys}


def write_site_island_manifest(assets: dict[str, str]) -> None:
	frappe.create_folder(get_site_islands_path())
	with open(get_site_islands_path(SITE_ISLANDS_MANIFEST), "w") as manifest:
		manifest.write(frappe.as_json(assets))
	frappe.client_cache.delete_value(SITE_ISLANDS_CACHE_KEY)


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
	assets_json = get_island_assets_json()
	js = assets_json.get(name + ISLAND_JS_SUFFIX) if name in get_ui_islands() else None
	if not js:
		frappe.throw(_('Island "{0}" is not on this site. Build the app that ships it.').format(name))

	return {"js": js, "css": assets_json.get(name + ISLAND_CSS_SUFFIX) or None}
