# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
"""Store Studio source files and validate their paths.

Repository apps (`is_standard`) keep files in `<frappe_app>/studio/<app>/`.
Editing these files requires developer mode. Database apps keep shared source
files in Studio App File records and can be edited without developer mode.
Their page scripts stay in Studio Page records but appear at the same paths
in the file explorer as repository page scripts.

Both app types can produce a Vite build. A database app can also compile its
source in the browser when no build is available. The browser runs the source
as it is, so TypeScript and Vue single file components need a repository app.

Enabling export writes stored files to the repository and clears the file store.
Disabling export restores supported files to the database before deleting the
export folder. The file APIs in `frappe.studio.api` select the app's source store.
"""

import hashlib
import os
import posixpath
import re

import frappe
from frappe import _

# Allow client source files only. Files that execute on the server, such as Python files,
# must be edited in the repository.
ALLOWED_STUDIO_FILE_EXTENSIONS = {".ts", ".js", ".vue", ".json", ".css"}
# The browser links and runs a database app's source as it is. TypeScript and Vue single file
# components need the repository's build, so the database store does not keep them.
ALLOWED_STORED_FILE_EXTENSIONS = {".js", ".json", ".css"}


def uses_db_files(studio_app: str) -> bool:
	"""Return whether the app uses database source storage. Return False for a missing app."""
	is_standard = frappe.db.get_value("Studio App", studio_app, "is_standard")
	return is_standard == 0


def is_page_script_path(path: str) -> bool:
	"""Match `studio_page/<stem>/<stem>.js`, the page script path used by both source stores.

	A repository app may still hold a page script written in TypeScript.
	"""
	return bool(re.fullmatch(r"studio_page/([^/]+)/\1\.(js|ts)", path))


def page_script_owner(studio_app: str, file_path: str) -> str | None:
	"""Return the page that owns this script path, or None if no page matches."""
	path = normalize_path(file_path)
	return page_script_paths(studio_app).get(path) if is_page_script_path(path) else None


def page_script_paths(studio_app: str) -> dict[str, str]:
	"""Map each exported page script path to its Studio Page name.

	Database page scripts stay on their page records. The file explorer lists them
	at their export paths so both app types show the same file layout.
	"""
	pages = frappe.get_all(
		"Studio Page",
		filters={"studio_app": studio_app, "page_title": ("is", "set")},
		fields=["name", "page_title"],
	)
	return {f"studio_page/{(stem := frappe.scrub(page.page_title))}/{stem}.js": page.name for page in pages}


def list_store_tree(studio_app: str) -> list[dict]:
	"""Return stored files and page script paths in the disk explorer's tree format."""
	stored = frappe.get_all("Studio App File", filters={"studio_app": studio_app}, pluck="file_path")
	files = set(stored) | page_script_paths(studio_app).keys()
	folders = set()
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
	"""Return stored source files and their content hashes for the browser compiler."""
	rows = frappe.get_all(
		"Studio App File",
		filters={"studio_app": studio_app},
		fields=["file_path", "content"],
		order_by="file_path",
	)
	return [
		{"path": row.file_path, "content": row.content or "", "hash": file_hash(row.content or "")}
		for row in rows
	]


def read_store_file(studio_app: str, file_path: str) -> str | None:
	"""Read source from the file store or its owning page. Return None for a missing file."""
	page = page_script_owner(studio_app, file_path)
	if page:
		return frappe.db.get_value("Studio Page", page, "script") or ""
	row = get_store_row(studio_app, file_path)
	if not row:
		return None
	return row.content or ""


def write_store_file(studio_app: str, file_path: str, content: str, known_hash: str | None = None) -> None:
	"""Save source to the file store or its owning page, creating a file if needed.

	If `known_hash` is supplied, reject the write when the existing content has changed.
	"""
	if not isinstance(content, str):
		frappe.throw(_("Invalid file content."))
	page = page_script_owner(studio_app, file_path)
	if page:
		return write_page_script(page, content, known_hash)
	row = get_store_row(studio_app, file_path)
	if not row:
		insert_store_row(studio_app, file_path, content)
		return

	if known_hash and file_hash(row.content or "") != known_hash:
		frappe.throw(_("{0} changed since you opened it.").format(file_path))
	doc = frappe.get_doc("Studio App File", row.name)
	doc.content = content
	doc.save()


def write_page_script(page: str, content: str, known_hash: str | None = None) -> None:
	"""Save through the owning Studio Page so rendering and export use the updated script."""
	doc = frappe.get_doc("Studio Page", page)
	if known_hash and file_hash(doc.script or "") != known_hash:
		frappe.throw(_("{0} changed since you opened it.").format(doc.page_title))
	doc.script = content
	doc.save()


def create_store_file(studio_app: str, file_path: str) -> None:
	if store_path_exists(studio_app, file_path):
		frappe.throw(_("{0} already exists.").format(file_path))
	insert_store_row(studio_app, file_path, "")


def rename_store_path(studio_app: str, file_path: str, new_path: str) -> None:
	"""Rename a stored file or a folder and all its descendants."""
	old = normalize_path(file_path)
	new = normalize_path(new_path)
	if page_script_owner(studio_app, old) or page_script_owner(studio_app, new):
		frappe.throw(_("A page script is named after its page. Rename the page instead."))
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
	"""Delete a stored file or a folder and all its contents.

	For a page script, clear the script on its owning page instead.
	"""
	path = normalize_path(file_path)
	page = page_script_owner(studio_app, path)
	if page:
		return write_page_script(page, "")
	row = get_store_row(studio_app, path)
	children = get_store_rows_under(studio_app, path)
	if not row and not children:
		frappe.throw(_("Not found: {0}").format(file_path))
	for child in children:
		frappe.delete_doc("Studio App File", child.name)
	if row:
		frappe.delete_doc("Studio App File", row.name)


def store_path_exists(studio_app: str, path: str) -> bool:
	"""Check whether a stored entry, page script or descendant already uses this path."""
	if page_script_owner(studio_app, path):
		return True
	return bool(get_store_row(studio_app, path) or get_store_rows_under(studio_app, path))


def get_store_row(studio_app: str, file_path: str):
	rows = frappe.get_all(
		"Studio App File",
		filters={"studio_app": studio_app, "file_path": normalize_path(file_path)},
		fields=["name", "file_path", "content"],
		limit=1,
	)
	return rows[0] if rows else None


def get_store_rows_under(studio_app: str, folder_path: str) -> list[frappe._dict]:
	"""Find entries under a folder. Compare paths in Python because SQL LIKE treats `_` as a wildcard."""
	prefix = normalize_path(folder_path) + "/"
	rows = frappe.get_all("Studio App File", filters={"studio_app": studio_app}, fields=["name", "file_path"])
	return [row for row in rows if row.file_path.startswith(prefix)]


def insert_store_row(studio_app: str, file_path: str, content: str) -> None:
	frappe.get_doc(
		doctype="Studio App File", studio_app=studio_app, file_path=file_path, content=content
	).insert()


def export_store_to_disk(app) -> None:
	"""Copy stored files to the export folder, then clear the database file store.

	Keep identical existing files. Abort if an existing file has different content.
	"""
	rows = frappe.get_all(
		"Studio App File", filters={"studio_app": app.name}, fields=["file_path", "content"]
	)
	if not rows:
		return
	app.write_files([{"path": row.file_path, "content": row.content or ""} for row in rows])
	frappe.db.delete("Studio App File", {"studio_app": app.name})


def restore_store_from_disk(app) -> None:
	"""Restore supported source files before disabling export deletes the folder.

	Restore page scripts separately to their page records. Skip generated JSON files,
	which the next export recreates from the database.
	"""
	root = app.get_folder_path()
	if not os.path.isdir(root):
		return
	for dirpath, _dirnames, filenames, folder in walk_export_folder(root):
		if folder.startswith("studio_page"):
			continue
		for filename in filenames:
			path = f"{folder}/{filename}" if folder else filename
			if not is_storable_file(app.name, path):
				continue
			write_store_file(app.name, path, frappe.read_file(os.path.join(dirpath, filename)) or "")


def walk_export_folder(root: str):
	"""Walk source directories, skipping hidden folders, node_modules and __pycache__.

	Include each directory's path relative to the export root; use "" for the root.
	"""
	for dirpath, dirnames, filenames in os.walk(root):
		dirnames[:] = [
			name
			for name in dirnames
			if not name.startswith(".") and name not in ("node_modules", "__pycache__")
		]
		folder = os.path.relpath(dirpath, root).replace(os.sep, "/")
		yield dirpath, dirnames, filenames, "" if folder == "." else folder


def discarded_export_files(app) -> list[str]:
	"""List files that disabling export would delete without preserving their content.

	The store accepts only supported source extensions outside `studio_page/`.
	Assets, Tailwind config and extra files beside pages may need separate handling.
	"""
	# A database app has no Frappe app from which to resolve an export folder.
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
	"""Check whether export recreates this file or a page record preserves its source."""
	name = posixpath.basename(path)
	if name.startswith(".") or name == "tsconfig.json" or is_export_doc_file(studio_app, path):
		return True
	# Studio Page.restore_script_from_file preserves page scripts before the folder is deleted.
	return is_page_script_path(path)


def is_storable_file(studio_app: str, path: str) -> bool:
	"""Check whether the file store supports this source file and Studio does not generate it."""
	name = posixpath.basename(path)
	if name.startswith(".") or name == "tsconfig.json" or name.lower() == "tailwind.config.js":
		return False
	if posixpath.splitext(name)[1].lower() not in ALLOWED_STORED_FILE_EXTENSIONS:
		return False
	return not path.startswith("studio_page/") and not is_export_doc_file(studio_app, path)


def normalize_path(file_path: str) -> str:
	"""Return a relative path with forward slashes and reject paths that need further normalization.

	The database store must validate paths itself because it cannot use filesystem resolution.
	"""
	if file_path is not None and not isinstance(file_path, str):
		frappe.throw(_("Invalid file path: {0}").format(file_path), frappe.PermissionError)
	path = (file_path or "").strip().strip("/")
	first_segment = path.split("/", 1)[0]
	if not path or "\\" in path or first_segment == ".." or posixpath.normpath(path) != path:
		frappe.throw(_("Invalid file path: {0}").format(file_path), frappe.PermissionError)
	return path


def file_hash(content: str) -> str:
	"""Return a content hash for detecting changes since the last read."""
	return hashlib.sha1(content.encode("utf-8")).hexdigest()


def validate_allowed_extension(file_path: str, allowed: set[str] | None = None) -> None:
	extension = os.path.splitext(file_path)[1].lower()
	if extension in (allowed or ALLOWED_STUDIO_FILE_EXTENSIONS):
		return
	if extension == ".vue":
		frappe.throw(
			_("A database app cannot hold Vue components. Export the app to a repository to add one.")
		)
	if extension == ".ts":
		frappe.throw(
			_(
				"A database app has no TypeScript compiler. Write JavaScript, or export the app to a repository."
			)
		)
	frappe.throw(_("Editing {0} files is not allowed.").format(extension or "these"))


def validate_folder_names(file_path: str) -> None:
	"""Keep source extensions out of folder names, so no file path can contain another file."""
	for folder in posixpath.dirname(file_path).split("/"):
		extension = posixpath.splitext(folder)[1].lower()
		if extension in ALLOWED_STUDIO_FILE_EXTENSIONS:
			frappe.throw(_("{0} is a folder, so its name cannot end with {1}.").format(folder, extension))


def is_export_doc_file(studio_app: str, file_path: str) -> bool:
	normalized = file_path.strip("/")
	if not normalized.lower().endswith(".json"):
		return False
	# Page and component JSON files use their own folders. App JSON uses <scrub(app)>.json at the root.
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
	# Tailwind config executes on the server, so require repository edits.
	# Match names without case to cover case-insensitive filesystems.
	if os.path.basename(file_path).lower() == "tailwind.config.js":
		frappe.throw(_("{0} runs at build time; edit it in the repository.").format(file_path))


def validate_folder_removable(file_path: str) -> None:
	if is_export_folder(file_path):
		frappe.throw(_("{0} is managed by Studio and can't be removed or renamed.").format(file_path))
