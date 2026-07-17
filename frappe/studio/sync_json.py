"""Import a single exported studio JSON file into the DB.

`sync.py` walks whole trees on migrate; this imports one file at a time, so changes made on disk
(by an editor, the CLI or an AI agent) can be picked up as they happen. See `watch.py`.
"""

import os

import frappe
from frappe.modules.import_file import calculate_hash, import_file_by_path

# Layout written by the exporters — see StudioApp.get_folder_path and StudioPage.get_folder_path:
#   <frappe_app>/studio/<studio_app>/<studio_app>.json                -> Studio App
#   <frappe_app>/studio/<studio_app>/studio_page/<stem>/<stem>.json   -> Studio Page
#   <frappe_app>/studio/<studio_app>/studio_components/<name>.json    -> Studio Component
PAGE_FOLDER = "studio_page"
COMPONENT_FOLDER = "studio_components"

# Hash of each file studio last exported, keyed by path. Lets the watcher tell its own writes
# apart from a real edit.
EXPORTED_HASHES_KEY = "studio_exported_file_hashes"


def sync_file(path: str) -> str | None:
	"""Import an exported studio JSON file. Return the doctype synced, or None if nothing was.

	Nothing is synced when `path` isn't a studio document, when it has since been removed — a file
	can be deleted between a watch event and the import — or when it's an echo of studio's own
	export.
	"""
	doctype = get_doctype_from_path(path)
	if not doctype or not os.path.exists(path) or is_echo(path):
		return None

	# `force` because editing JSON on disk doesn't bump its `modified`, and import_file_by_path
	# otherwise skips any doc whose DB timestamp isn't older than the file's.
	return doctype if import_file_by_path(path, force=True) else None


def cache_exported_file_hash(path: str):
	"""Record what studio just wrote to `path` so syncing it back is skipped as an echo."""
	frappe.cache.hset(EXPORTED_HASHES_KEY, path, calculate_hash(path))


def is_echo(path: str) -> bool:
	"""True if `path` still holds exactly what studio last exported to it.

	Saving a doc exports it (`StudioPage.on_update` -> `export_page`), which trips the watcher.
	Re-importing that write would be a pointless delete+insert of the doc just saved, and could
	clobber a save that lands while it's in flight. Anything else on disk is a genuine edit.
	"""
	exported_hash = frappe.cache.hget(EXPORTED_HASHES_KEY, path)
	return bool(exported_hash) and exported_hash == calculate_hash(path)


def get_doctype_from_path(path: str) -> str | None:
	"""Match a path against the export layout above. None if it isn't a studio document."""
	parts = get_studio_relative_parts(path)
	if not parts or not parts[-1].endswith(".json"):
		return None

	studio_app, *rest = parts
	if rest == [f"{studio_app}.json"]:
		return "Studio App"
	# a page's folder and file share the stem; anything else is not a page export
	if len(rest) == 3 and rest[0] == PAGE_FOLDER and rest[1] == rest[2].removesuffix(".json"):
		return "Studio Page"
	if len(rest) == 2 and rest[0] == COMPONENT_FOLDER:
		return "Studio Component"
	return None


def get_studio_relative_parts(path: str) -> list[str] | None:
	"""Split `path` into parts relative to the `<app>/studio` folder holding it, e.g.
	["notes", "studio_page", "inbox", "inbox.json"]. None if it isn't under one."""
	path = os.path.abspath(path)
	for folder in get_studio_folders():
		if path.startswith(folder + os.sep):
			return path[len(folder) + 1 :].split(os.sep)
	return None


def get_studio_folders() -> list[str]:
	"""The `<app>/studio` source path of every installed app that has one."""
	folders = []
	for app in frappe.get_installed_apps():
		path = frappe.get_app_source_path(app, "studio")
		if os.path.exists(path):
			folders.append(os.path.abspath(path))
	return folders
