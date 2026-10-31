# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The app layer of `Doctype View`: one JSON file per saved view, named by its key."""

import functools
import json
import os
from typing import NamedTuple

import frappe
from frappe.modules.utils import get_module_list
from frappe.utils.caching import request_cache

from .doctype_view import SETTINGS_SIZE_LIMIT, VIEW_TYPES

FILE_KEYS = frozenset({"label", "type", "default", "settings"})


class AppView(NamedTuple):
	app: str
	doctype: str | None  # `None` for a doctype made on the site: no folder holds its name
	key: str
	label: str
	type: str
	default: bool
	path: str


class ViewFileError(ValueError):
	pass


def app_views(doctype: str) -> dict[str, AppView]:
	"""`{key: view}` of the views the site's apps ship for `doctype`, one per key after clashes."""
	return current_index().views.get(frappe.scrub(doctype), {})


def app_view_settings(doctype: str, key: str) -> dict | None:
	"""The `settings` of the app view at `key`, read from its file; `None` when no app ships one."""
	view = app_views(doctype).get(key)
	if not view:
		return None
	try:
		stat = os.stat(view.path)
		return json.loads(load_settings(view.path, stat.st_mtime_ns, stat.st_size))
	except (OSError, ViewFileError):
		return None


def app_defaults(app: str | None = None) -> dict[str, str]:
	"""`{doctype: key}` of each doctype's app default: `app`'s, else the one its own app ships."""
	return {name: view.key for name, view in named(current_index().defaults_in(app))}


def app_view_doctypes() -> list[str]:
	"""The names of the doctypes the site's apps ship views for."""
	firsts = [(doctype, next(iter(views.values()))) for doctype, views in current_index().views.items()]
	return [name for name, _view in named(firsts)]


def named(views: list[tuple[str, "AppView"]]) -> list[tuple[str, "AppView"]]:
	"""Each `(scrubbed doctype, view)` as `(doctype name, view)`; a doctype made on the site is named from the database."""
	names = site_doctype_names() if any(view.doctype is None for _doctype, view in views) else {}
	return [(name, view) for doctype, view in views if (name := view.doctype or names.get(doctype))]


@request_cache
def site_doctype_names() -> dict[str, str]:
	return {frappe.scrub(name): name for name in frappe.get_all("DocType", pluck="name")}


@request_cache
def current_index() -> "ViewIndex":
	apps = tuple(frappe.get_active_apps(_ensure_on_bench=True))
	if not frappe.conf.developer_mode:
		return deployed_index(apps)
	# A deploy restarts the workers; in developer mode an edited, added or deleted file applies at once.
	return developer_index(apps, tuple((folder.path, *stamp(folder.path)) for folder in view_folders(apps)))


@functools.cache
def deployed_index(apps: tuple[str, ...]) -> "ViewIndex":
	"""One per set of apps, so the sites of a bench that install different apps never evict each other."""
	return ViewIndex(apps)


@functools.lru_cache(maxsize=8)
def developer_index(apps: tuple[str, ...], _stamp: tuple) -> "ViewIndex":
	return ViewIndex(apps)


class ViewFolder(NamedTuple):
	app: str
	doctype: str  # scrubbed: a `custom/` folder names its doctype by its folder name only
	path: str


class ViewIndex:
	"""Every app view of the site's apps by doctype; clashes and refused files are logged once, on build."""

	def __init__(self, apps: tuple[str, ...]):
		self.apps = apps
		self.doctype_folders = doctype_folders(apps)
		self.refused: list[str] = []
		self.clashes: list[str] = []
		self.views: dict[str, dict[str, AppView]] = {}
		self.defaults: dict[tuple[str, str], AppView] = {}
		for folder in sorted(view_folders(apps), key=self.precedence):
			self.add_folder(folder)
		for problem in (*self.refused, *self.clashes):
			frappe.logger("desk").warning(problem)

	def precedence(self, folder: ViewFolder) -> tuple[bool, int]:
		"""The doctype's own app first, then the others in app order."""
		return folder.app != self.owner(folder.doctype), self.apps.index(folder.app)

	def owner(self, doctype: str) -> str | None:
		return self.doctype_folders[doctype].app if doctype in self.doctype_folders else None

	def add_folder(self, folder: ViewFolder):
		name = self.doctype_name(folder.doctype)
		for path in sorted(view_files(folder.path)):
			try:
				view = read_view(folder.app, name, path)
			except (OSError, ViewFileError) as error:
				self.refused.append(f"App view file {path} is refused: {error}")
				continue
			self.add(folder.doctype, view)

	def doctype_name(self, doctype: str) -> str | None:
		"""The doctype's name from its own folder's JSON; a doctype made on the site has no folder."""
		if doctype not in self.doctype_folders:
			return None
		path = os.path.join(self.doctype_folders[doctype].path, f"{doctype}.json")
		try:
			return load_doctype_name(path, os.stat(path).st_mtime_ns) or None
		except (OSError, ViewFileError):
			return None

	def add(self, doctype: str, view: AppView):
		views = self.views.setdefault(doctype, {})
		if winner := views.get(view.key):
			self.clashes.append(
				f"App view {view.key!r} of {doctype} ships in {winner.app} and {view.app}; {winner.app}'s is used."
			)
			return
		views[view.key] = view
		if view.default:
			self.add_default(doctype, view)

	def add_default(self, doctype: str, view: AppView):
		address = (view.app, doctype)
		if first := self.defaults.get(address):
			self.refused.append(
				f"App view {view.path} is a second default of {doctype} in {view.app}; {first.key!r} is the default."
			)
			return
		self.defaults[address] = view

	def defaults_in(self, app: str | None) -> list[tuple[str, AppView]]:
		"""`(scrubbed doctype, view)` of each doctype's default: `app`'s, else its own app's."""
		doctypes = {doctype for _app, doctype in self.defaults}
		found = (
			(doctype, self.defaults.get((app, doctype)) or self.defaults.get((self.owner(doctype), doctype)))
			for doctype in doctypes
		)
		return [(doctype, view) for doctype, view in found if view]


def read_view(app: str, doctype: str, path: str) -> AppView:
	stat = os.stat(path)
	label, type, default = load_head(path, stat.st_mtime_ns, stat.st_size)
	return AppView(app, doctype, view_key(path), label, type, default, path)


@functools.lru_cache(maxsize=512)
def load_head(path: str, mtime_ns: int, size: int) -> tuple[str, str, bool]:
	"""The file's label, type and default flag, after the checks a `Doctype View` row gets."""
	data = load_file(path)
	check_key(view_key(path))
	if not isinstance(data, dict):
		raise ViewFileError("a view file is one object")
	if unknown := sorted(set(data) - FILE_KEYS):
		raise ViewFileError(f"unknown keys {', '.join(unknown)}")
	if not isinstance(data.get("label"), str) or not data["label"].strip():
		raise ViewFileError("a view needs a label")
	if data.get("type") not in VIEW_TYPES:
		raise ViewFileError(f"{data.get('type')!r} is not a view type")
	if not isinstance(data.get("default", False), bool):
		raise ViewFileError("`default` is true or false")
	check_settings(data.get("settings", {}))
	return data["label"], data["type"], data.get("default", False)


@functools.lru_cache(maxsize=256)
def load_settings(path: str, mtime_ns: int, size: int) -> str:
	"""The file's settings, checked again: the file may have changed since the index read it."""
	data = load_file(path)
	settings = data.get("settings", {}) if isinstance(data, dict) else None
	check_settings(settings)
	return json.dumps(settings)


def check_key(key: str):
	# Imported here: `key_space` reads this module's index.
	from .key_space import RESERVED_KEYS, url_safe

	if not key:
		raise ViewFileError("a view file needs a name")
	if key in RESERVED_KEYS:
		raise ViewFileError(f"{key!r} is a view type's name")
	if url_safe(key) != key:
		raise ViewFileError(f"{key!r} is not a view key: lower-case letters, digits and dashes")


def check_settings(settings):
	if not isinstance(settings, dict):
		raise ViewFileError("the settings of a view are one object")
	if len(json.dumps(settings).encode()) > SETTINGS_SIZE_LIMIT:
		raise ViewFileError(f"the settings are larger than {SETTINGS_SIZE_LIMIT // 1024} KB")


def view_folders(apps: tuple[str, ...]) -> list[ViewFolder]:
	"""Each `views` folder of the apps' modules: beside a doctype the app owns, or in its `custom/` folder."""
	folders = []
	for app, module_path in module_paths(apps):
		for doctype in subfolders(os.path.join(module_path, "doctype")):
			folders.append(
				ViewFolder(app, doctype, os.path.join(module_path, "doctype", doctype, "frontend", "views"))
			)
		for doctype in subfolders(os.path.join(module_path, "custom")):
			folders.append(ViewFolder(app, doctype, os.path.join(module_path, "custom", doctype, "views")))
	return [folder for folder in folders if os.path.isdir(folder.path)]


def doctype_folders(apps: tuple[str, ...]) -> dict[str, ViewFolder]:
	"""`{scrubbed doctype: its folder}`; the first app in app order holds a name two apps share."""
	folders = {}
	for app, module_path in module_paths(apps):
		for doctype in subfolders(os.path.join(module_path, "doctype")):
			folders.setdefault(
				doctype, ViewFolder(app, doctype, os.path.join(module_path, "doctype", doctype))
			)
	return folders


@functools.lru_cache(maxsize=256)
def load_doctype_name(path: str, _mtime_ns: int) -> str:
	return load_file(path).get("name") or ""


def module_paths(apps: tuple[str, ...]) -> list[tuple[str, str]]:
	return [
		(app, os.path.join(frappe.get_app_path(app), frappe.scrub(module)))
		for app in dict.fromkeys(apps)
		for module in get_module_list(app)
	]


def load_file(path: str):
	# App source path from an installed app's module folder; never request-derived.
	with open(path) as f:  # nosemgrep
		try:
			return json.load(f)
		except ValueError as error:
			raise ViewFileError(f"not JSON: {error}") from error


def view_files(folder: str) -> list[str]:
	return [entry.path for entry in os.scandir(folder) if entry.is_file() and entry.name.endswith(".json")]


def view_key(path: str) -> str:
	return os.path.splitext(os.path.basename(path))[0]


def subfolders(path: str) -> list[str]:
	if not os.path.isdir(path):
		return []
	return [
		entry.name for entry in os.scandir(path) if entry.is_dir() and not entry.name.startswith(("_", "."))
	]


def stamp(folder: str) -> tuple:
	"""The folder's and its files' modified times: a new, deleted or edited file changes it."""
	files = sorted(view_files(folder))
	return (os.stat(folder).st_mtime_ns, *((path, *file_stamp(path)) for path in files))


def file_stamp(path: str) -> tuple[int, int]:
	stat = os.stat(path)
	return stat.st_mtime_ns, stat.st_size
