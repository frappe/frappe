# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
"""Where a Studio app's source files live, and the path rules they follow.

A Studio app's loose source files — `.vue` components, composables, `router.ts`, stylesheets —
live either in a repository or in the database:

* **Repository app** (`is_standard`): the files sit in `<frappe_app>/studio/<app>/`, Vite builds
  them, and git reviews them. Editing needs a bench in developer mode.
* **Database app**: the files sit in `Studio App File` records and the browser compiles them, so
  the app is built and edited on the site it runs on — no repository, no developer mode, no
  build step.

Both store the same files in the same layout, so moving an app between them is a file copy:
enabling export flushes the store into the app folder and empties it, and disabling export loads
the folder back in. The file explorer APIs in `frappe/studio/api.py` route to whichever side owns
the app's files.
"""

import hashlib
import os
import posixpath
import re

import frappe
from frappe import _

# Extensions the file explorer and the file store accept. Deliberately excludes `.py` and anything
# else that executes on the server — these files are bundled into the app build, or compiled in
# the browser.
ALLOWED_STUDIO_FILE_EXTENSIONS = {".ts", ".js", ".vue", ".json", ".css"}


def uses_db_files(studio_app: str) -> bool:
	"""Whether the app keeps its source files in the DB store rather than in a repository.
	A missing app is not a store: callers fall through to the disk jail, which rejects it."""
	is_standard = frappe.db.get_value("Studio App", studio_app, "is_standard")
	return is_standard == 0


def list_store_tree(studio_app: str) -> list[dict]:
	"""The store's file tree, in the same shape the disk explorer returns."""
	rows = frappe.get_all(
		"Studio App File", filters={"studio_app": studio_app}, fields=["file_path", "is_folder"]
	)
	files = {row.file_path for row in rows if not row.is_folder}
	folders = {row.file_path for row in rows if row.is_folder}
	for path in files:
		folder = posixpath.dirname(path)
		while folder:
			folders.add(folder)
			folder = posixpath.dirname(folder)
	return build_tree("", folders, files)


def build_tree(parent: str, folders: set[str], files: set[str]) -> list[dict]:
	nodes = [
		{
			"label": posixpath.basename(path),
			"path": path,
			"is_folder": True,
			"children": build_tree(path, folders, files),
		}
		for path in folders
		if posixpath.dirname(path) == parent
	]
	nodes += [
		{"label": posixpath.basename(path), "path": path, "is_folder": False, "children": []}
		for path in files
		if posixpath.dirname(path) == parent
	]
	nodes.sort(key=lambda node: (not node["is_folder"], node["label"].lower()))
	return nodes


def get_store_files(studio_app: str) -> list[dict]:
	"""Every file in the store with its content hash — what the browser compiles."""
	rows = frappe.get_all(
		"Studio App File",
		filters={"studio_app": studio_app, "is_folder": 0},
		fields=["file_path", "content"],
		order_by="file_path",
	)
	return [
		{"path": row.file_path, "content": row.content or "", "hash": file_hash(row.content or "")}
		for row in rows
	]


def read_store_file(studio_app: str, file_path: str) -> str | None:
	"""The file's content, or None when the store has no such file."""
	row = get_store_row(studio_app, file_path)
	if not row or row.is_folder:
		return None
	return row.content or ""


def write_store_file(studio_app: str, file_path: str, content: str, known_hash: str | None = None) -> None:
	"""Write content to a stored file, creating it if needed. If known_hash is given and the
	stored content changed since it was read, refuse rather than clobber."""
	if not isinstance(content, str):
		frappe.throw(_("Invalid file content."))
	row = get_store_row(studio_app, file_path)
	if row and row.is_folder:
		frappe.throw(_("{0} is a folder.").format(file_path))
	if not row:
		insert_store_row(studio_app, file_path, content)
		return

	if known_hash and file_hash(row.content or "") != known_hash:
		frappe.throw(_("{0} changed since you opened it.").format(file_path))
	doc = frappe.get_doc("Studio App File", row.name)
	doc.content = content
	doc.save()


def create_store_file(studio_app: str, file_path: str) -> None:
	if store_path_exists(studio_app, file_path):
		frappe.throw(_("{0} already exists.").format(file_path))
	insert_store_row(studio_app, file_path, "")


def create_store_folder(studio_app: str, folder_path: str) -> None:
	if store_path_exists(studio_app, folder_path):
		frappe.throw(_("{0} already exists.").format(folder_path))
	insert_store_row(studio_app, folder_path, None, is_folder=True)


def rename_store_path(studio_app: str, file_path: str, new_path: str) -> None:
	"""Rename a stored file, or a folder with everything under it."""
	old = normalize_path(file_path)
	new = normalize_path(new_path)
	row = get_store_row(studio_app, old)
	children = get_store_rows_under(studio_app, old)
	if not row and not children:
		frappe.throw(_("Not found: {0}").format(file_path))
	if store_path_exists(studio_app, new):
		frappe.throw(_("{0} already exists.").format(new_path))

	for child in children:
		rename_store_row(child.name, new + child.file_path[len(old) :])
	if row:
		rename_store_row(row.name, new)


def rename_store_row(name: str, new_path: str) -> None:
	doc = frappe.get_doc("Studio App File", name)
	doc.file_path = new_path
	doc.save()


def delete_store_path(studio_app: str, file_path: str) -> None:
	"""Delete a stored file, or a folder with everything under it."""
	path = normalize_path(file_path)
	row = get_store_row(studio_app, path)
	children = get_store_rows_under(studio_app, path)
	if not row and not children:
		frappe.throw(_("Not found: {0}").format(file_path))
	for child in children:
		frappe.delete_doc("Studio App File", child.name)
	if row:
		frappe.delete_doc("Studio App File", row.name)


def store_path_exists(studio_app: str, path: str) -> bool:
	"""A path is taken by a row, or implicitly by being the folder of one."""
	return bool(get_store_row(studio_app, path) or get_store_rows_under(studio_app, path))


def get_store_row(studio_app: str, file_path: str):
	rows = frappe.get_all(
		"Studio App File",
		filters={"studio_app": studio_app, "file_path": normalize_path(file_path)},
		fields=["name", "file_path", "content", "is_folder"],
		limit=1,
	)
	return rows[0] if rows else None


def get_store_rows_under(studio_app: str, folder_path: str) -> list[frappe._dict]:
	"""Rows whose path lies under `folder_path` (checked in Python — LIKE would read `_` as a wildcard)."""
	prefix = normalize_path(folder_path) + "/"
	rows = frappe.get_all("Studio App File", filters={"studio_app": studio_app}, fields=["name", "file_path"])
	return [row for row in rows if row.file_path.startswith(prefix)]


def insert_store_row(studio_app: str, file_path: str, content: str | None, is_folder: bool = False) -> None:
	frappe.get_doc(
		doctype="Studio App File",
		studio_app=studio_app,
		file_path=file_path,
		content=content,
		is_folder=is_folder,
	).insert()


def export_store_to_disk(app) -> None:
	"""Write every stored file verbatim into the app's export folder and empty the store — from
	then on the repository owns the files. Identical existing files are kept; a conflicting one
	aborts."""
	rows = frappe.get_all(
		"Studio App File",
		filters={"studio_app": app.name},
		fields=["file_path", "content", "is_folder"],
	)
	if not rows:
		return
	for row in rows:
		if row.is_folder:
			frappe.create_folder(app.resolve_file_path(row.file_path))
	app.write_files(
		[{"path": row.file_path, "content": row.content or ""} for row in rows if not row.is_folder]
	)
	frappe.db.delete("Studio App File", {"studio_app": app.name})


def restore_store_from_disk(app) -> None:
	"""Load the export folder's loose files back into the store, called before the folder is
	deleted when export is disabled. Export-managed files stay out: page scripts go back into
	the page docs and the JSONs are regenerated from the DB."""
	root = app.get_folder_path()
	if not os.path.isdir(root):
		return
	for dirpath, dirnames, filenames, folder in walk_export_folder(root):
		if folder.startswith("studio_page"):
			continue
		if folder and not dirnames and not filenames and not store_path_exists(app.name, folder):
			create_store_folder(app.name, folder)
		for filename in filenames:
			path = f"{folder}/{filename}" if folder else filename
			if not is_storable_file(app.name, path):
				continue
			write_store_file(app.name, path, frappe.read_file(os.path.join(dirpath, filename)) or "")


def walk_export_folder(root: str):
	"""Walk an export folder past dot and dependency directories, yielding each directory with
	its path relative to the root ("" at the top)."""
	for dirpath, dirnames, filenames in os.walk(root):
		dirnames[:] = [
			name
			for name in dirnames
			if not name.startswith(".") and name not in ("node_modules", "__pycache__")
		]
		folder = os.path.relpath(dirpath, root).replace(os.sep, "/")
		yield dirpath, dirnames, filenames, "" if folder == "." else folder


def discarded_export_files(app) -> list[str]:
	"""Export-folder files that disabling export would delete rather than store. The store takes
	only a few extensions and nothing under `studio_page/`, so assets, the Tailwind config and
	anything an author keeps beside a page have no home in the database."""
	# an app with no frappe_app has no folder path to compute, so isdir below never gets a chance
	if not app.frappe_app:
		return []
	root = app.get_folder_path()
	if not os.path.isdir(root):
		return []
	discarded = []
	for _dirpath, _dirnames, filenames, folder in walk_export_folder(root):
		for filename in filenames:
			path = f"{folder}/{filename}" if folder else filename
			if not is_storable_file(app.name, path) and not is_regenerated_file(app.name, path):
				discarded.append(path)
	return sorted(discarded)


def is_regenerated_file(studio_app: str, path: str) -> bool:
	"""A file the next export writes again from the database, so dropping it loses no work."""
	name = posixpath.basename(path)
	if name.startswith(".") or name == "tsconfig.json" or is_export_doc_file(studio_app, path):
		return True
	# studio_page/<stem>/<stem>.ts goes back into its page doc, see Studio Page.restore_script_from_file
	return bool(re.fullmatch(r"studio_page/([^/]+)/\1\.ts", path))


def is_storable_file(studio_app: str, path: str) -> bool:
	"""Whether a disk file belongs in the store: an editable loose file, not an export-managed
	or generated one."""
	name = posixpath.basename(path)
	if name.startswith(".") or name == "tsconfig.json" or name.lower() == "tailwind.config.js":
		return False
	if posixpath.splitext(name)[1].lower() not in ALLOWED_STUDIO_FILE_EXTENSIONS:
		return False
	return not path.startswith("studio_page/") and not is_export_doc_file(studio_app, path)


def normalize_path(file_path: str) -> str:
	"""A clean, relative, forward-slash path. The DB store has no filesystem to resolve tricks,
	so only already-normal paths are accepted."""
	if file_path is not None and not isinstance(file_path, str):
		frappe.throw(_("Invalid file path: {0}").format(file_path), frappe.PermissionError)
	path = (file_path or "").strip().strip("/")
	first_segment = path.split("/", 1)[0]
	if not path or "\\" in path or first_segment == ".." or posixpath.normpath(path) != path:
		frappe.throw(_("Invalid file path: {0}").format(file_path), frappe.PermissionError)
	return path


def file_hash(content: str) -> str:
	"""Short content fingerprint used to detect edits that happened since the last read."""
	return hashlib.sha1(content.encode("utf-8")).hexdigest()


def validate_allowed_extension(file_path: str) -> None:
	extension = os.path.splitext(file_path)[1].lower()
	if extension not in ALLOWED_STUDIO_FILE_EXTENSIONS:
		frappe.throw(_("Editing {0} files is not allowed.").format(extension or "these"))


def is_export_doc_file(studio_app: str, file_path: str) -> bool:
	normalized = file_path.strip("/")
	if not normalized.lower().endswith(".json"):
		return False
	# pages/components live in their folders; the app itself exports to <scrub(app)>.json at the root
	return (
		normalized.startswith("studio_page/")
		or normalized.startswith("studio_components/")
		or normalized == f"{frappe.scrub(studio_app)}.json"
	)


def is_export_folder(file_path: str) -> bool:
	normalized = file_path.strip("/")
	return normalized in ("studio_page", "studio_components") or bool(
		re.fullmatch(r"studio_page/[^/]+", normalized)
	)


def validate_editable(studio_app: str, file_path: str) -> None:
	if is_export_doc_file(studio_app, file_path):
		frappe.throw(_("{0} is generated by Studio and is read-only.").format(file_path))
	# the build runs this file on the server, so only the repository may author it;
	# compare case-insensitively since macOS/Windows resolve Tailwind.Config.js to the same file
	if os.path.basename(file_path).lower() == "tailwind.config.js":
		frappe.throw(_("{0} runs at build time; edit it in the repository.").format(file_path))


def validate_folder_removable(file_path: str) -> None:
	if is_export_folder(file_path):
		frappe.throw(_("{0} is managed by Studio and can't be removed or renamed.").format(file_path))
