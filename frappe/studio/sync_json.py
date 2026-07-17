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

# Hash of each file as of the last time it and the DB agreed, keyed by path. Lets the watcher tell
# a write it already knows about from a genuine edit.
SYNCED_HASHES_KEY = "studio_synced_file_hashes"


def sync_file(path: str) -> str | None:
	"""Import an exported studio JSON file. Return the doctype synced, or None if nothing was.

	Nothing is synced when `path` isn't a studio document, when it has since been removed — a file
	can be deleted between a watch event and the import — or when the DB already holds it.
	"""
	doctype = get_doctype_from_path(path)
	if not doctype or not os.path.exists(path) or is_in_sync(path):
		return None

	# `force` because editing JSON on disk doesn't bump its `modified`
	if not import_file_by_path(path, force=True):
		return None

	# Mirrors frappe stamping `migration_hash` after its own imports.
	cache_synced_file_hash(path)
	return doctype


def cache_synced_file_hash(path: str):
	"""Record `path`'s content now that it matches the DB, so syncing it back is skipped."""
	frappe.cache.hset(SYNCED_HASHES_KEY, path, calculate_hash(path))


def is_in_sync(path: str) -> bool:
	"""True if `path`'s content matches the DB, so syncing it back is skipped."""
	synced_hash = frappe.cache.hget(SYNCED_HASHES_KEY, path)
	return bool(synced_hash) and synced_hash == calculate_hash(path)


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
