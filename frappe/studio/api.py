import hashlib
import os
import re
import shutil
from typing import Literal

import frappe
from frappe import _
from frappe.model import display_fieldtypes, no_value_fields, table_fields

from studio.constants import STANDARD_COMPONENT_NAMES
from studio.utils import has_page_write_perm


@frappe.whitelist()
def get_docname(doctype: str, filters: dict | str) -> dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	# remove name filter if it is dynamic or empty - for fetching a document while testing
	if "name" in filters and (filters["name"].startswith(":") or not filters["name"]):
		del filters["name"]

	document = frappe.get_list(doctype, filters=filters, pluck="name", limit=1)
	return document[0] if document else None

	return None


@frappe.whitelist()
def get_doctype_fields(doctype: str) -> list[dict]:
	fields = frappe.get_meta(doctype).fields
	# find the name field
	name_field = next((field for field in fields if field.fieldname == "name"), None)
	if not name_field:
		name_field = frappe._dict(
			{
				"fieldname": "name",
				"fieldtype": "Data",
				"label": "ID",
			}
		)
		fields.append(name_field)

	return [
		field
		for field in fields
		if field.fieldtype not in ((set(no_value_fields) | set(display_fieldtypes)) - set(table_fields))
	]


@frappe.whitelist()
def get_whitelisted_methods(doctype: str) -> list[str]:
	from frappe import is_whitelisted
	from frappe.model.base_document import get_controller

	controller = get_controller(doctype)
	whitelisted_methods = []

	for method in controller.__dict__:
		if callable(getattr(controller, method)):
			try:
				is_whitelisted(getattr(controller, method))
				whitelisted_methods.append(method)
			except Exception:
				# not whitelisted
				continue

	return whitelisted_methods


@frappe.whitelist()
def get_sort_fields(doctype: str):
	fields = frappe.get_meta(doctype).fields
	fields = [field for field in fields if field.fieldtype not in no_value_fields]
	fields = [
		{
			"label": _(field.label),
			"value": field.fieldname,
			"fieldname": field.fieldname,
		}
		for field in fields
		if field.label and field.fieldname
	]

	standard_fields = [
		{"label": "Created On", "fieldname": "creation"},
		{"label": "Last Modified", "fieldname": "modified"},
		{"label": "Modified By", "fieldname": "modified_by"},
		{"label": "Owner", "fieldname": "owner"},
	]

	for field in standard_fields:
		field["label"] = _(field["label"])
		field["value"] = field["fieldname"]
		fields.append(field)

	return fields


@frappe.whitelist()
def check_app_permission() -> bool:
	if frappe.session.user == "Administrator":
		return True
	if frappe.has_permission("Studio App", ptype="write") and frappe.has_permission(
		"Studio Page", ptype="write"
	):
		return True
	return False


@frappe.whitelist()
def get_custom_vue_components(frappe_app: str) -> list[dict]:
	"""Discover custom Vue SFC components"""
	components = []
	seen_names = set()

	studio_folder = frappe.get_app_source_path(frappe_app, "studio")
	if not os.path.exists(studio_folder):
		return []

	def has_reserved_name(name: str) -> bool:
		if name in STANDARD_COMPONENT_NAMES:
			frappe.log_error(
				title="Studio: Custom component name conflict",
				message=f"Custom component '{component_name}' in {frappe_app}/{studio_app} "
				f"conflicts with a standard component. Skipping.",
			)
			return True
		return False

	def has_conflicting_name(name: str) -> bool:
		if name in seen_names:
			frappe.log_error(
				title="Studio: Duplicate custom component",
				message=f"Custom component '{component_name}' in {frappe_app}/{studio_app} "
				f"conflicts with another component. Skipping.",
			)
			return True
		return False

	for studio_app in os.listdir(studio_folder):
		studio_app_dir = os.path.join(studio_folder, studio_app)
		if not os.path.isdir(studio_app_dir):
			continue

		for dirpath, _dirnames, filenames in os.walk(studio_app_dir):
			for filename in sorted(filenames):
				if not filename.endswith(".vue"):
					continue

				component_name = filename[:-4]  # remove .vue
				if has_reserved_name(component_name) or has_conflicting_name(component_name):
					continue

				seen_names.add(component_name)
				file_path = os.path.join(dirpath, filename)

				components.append(
					{
						"component_name": component_name,
						"studio_app": studio_app,
						"file_path": file_path,
						"studio_file_path": os.path.relpath(file_path, studio_app_dir),
					}
				)

	return components


@frappe.whitelist()
def get_studio_page_scripts(frappe_app: str) -> list[dict]:
	"""Discover exported page scripts (<page>.ts) under <app>/studio/<studio_app>/studio_page/.

	Keyed by the page's docname (`page_name`, read from the sibling JSON) so the runtime can load
	a page's compiled setup() module by its docname.
	"""
	scripts = []

	studio_folder = frappe.get_app_source_path(frappe_app, "studio")
	if not os.path.exists(studio_folder):
		return []

	for studio_app in sorted(os.listdir(studio_folder)):
		page_folder = os.path.join(studio_folder, studio_app, "studio_page")
		if not os.path.isdir(page_folder):
			continue

		# each page is a folder holding <stem>.json + <stem>.ts
		for entry in sorted(os.listdir(page_folder)):
			page_dir = os.path.join(page_folder, entry)
			if not os.path.isdir(page_dir):
				continue

			file_path = os.path.join(page_dir, f"{entry}.ts")
			json_path = os.path.join(page_dir, f"{entry}.json")
			if not (os.path.exists(file_path) and os.path.exists(json_path)):
				continue
			page_name = frappe.parse_json(frappe.read_file(json_path)).get("page_name")
			if page_name:
				scripts.append(
					{
						"page_name": page_name,
						"frappe_app": frappe_app,
						"studio_app": studio_app,
						"file_path": file_path,
					}
				)

	return scripts


# ---------------------------------------------------------------------------
# Studio file explorer
#
# Read/write the code files (`.ts/.js/.vue/.json/.css`) under an exported app's
# `studio/<studio_app>/` folder, so developers can edit composables, stores, page
# scripts and components from Studio itself.
# ---------------------------------------------------------------------------
# Extensions a developer may read/write through the Studio file explorer. Deliberately excludes
# `.py` and anything else that executes on the server — these files are bundled into the app build.
ALLOWED_STUDIO_FILE_EXTENSIONS = {".ts", ".js", ".vue", ".json", ".css"}


@frappe.whitelist()
def list_studio_files(frappe_app: str, studio_app: str) -> list[dict]:
	"""Return the editable file tree under the exported app's studio folder."""
	_validate_studio_file_access()
	root = _studio_app_root(frappe_app, studio_app)
	if not os.path.isdir(root):
		return []
	return _build_studio_file_tree(root, root)


@frappe.whitelist()
def read_studio_file(frappe_app: str, studio_app: str, file_path: str) -> dict:
	"""Return a file's content plus a hash callers pass back to write_studio_file for conflict checks."""
	_validate_studio_file_access()
	_validate_allowed_extension(file_path)
	target = _resolve_studio_file(frappe_app, studio_app, file_path)
	if not os.path.isfile(target):
		frappe.throw(_("File not found: {0}").format(file_path))

	with open(target, encoding="utf-8") as f:
		content = f.read()
	return {"path": file_path, "content": content, "hash": _file_hash(content)}


@frappe.whitelist()
@has_page_write_perm()
def write_studio_file(
	frappe_app: str, studio_app: str, file_path: str, content: str, known_hash: str | None = None
) -> dict:
	"""Write content to a file (creating parent folders). If known_hash is given and the file changed
	on disk since it was read, refuse rather than clobber."""
	_validate_studio_file_access()
	_validate_allowed_extension(file_path)
	_validate_editable(studio_app, file_path)
	target = _resolve_studio_file(frappe_app, studio_app, file_path)

	if known_hash and os.path.isfile(target):
		with open(target, encoding="utf-8") as f:
			if _file_hash(f.read()) != known_hash:
				frappe.throw(_("{0} changed on disk since you opened it.").format(file_path))

	os.makedirs(os.path.dirname(target), exist_ok=True)
	with open(target, "w", encoding="utf-8") as f:
		f.write(content)
	return {"path": file_path, "hash": _file_hash(content)}


@frappe.whitelist()
@has_page_write_perm()
def create_studio_file(frappe_app: str, studio_app: str, file_path: str) -> dict:
	"""Create an empty editable file (and any parent folders); error if it already exists."""
	_validate_studio_file_access()
	_validate_allowed_extension(file_path)
	target = _resolve_studio_file(frappe_app, studio_app, file_path)
	if os.path.exists(target):
		frappe.throw(_("{0} already exists.").format(file_path))

	os.makedirs(os.path.dirname(target), exist_ok=True)
	with open(target, "w", encoding="utf-8") as f:
		f.write("")
	return {"path": file_path, "hash": _file_hash("")}


@frappe.whitelist()
@has_page_write_perm()
def create_studio_folder(frappe_app: str, studio_app: str, folder_path: str) -> dict:
	"""Create an empty folder (and any parent folders) within the app folder."""
	_validate_studio_file_access()
	target = _resolve_studio_file(frappe_app, studio_app, folder_path)
	if os.path.exists(target):
		frappe.throw(_("{0} already exists.").format(folder_path))
	os.makedirs(target)
	return {"path": folder_path}


@frappe.whitelist()
@has_page_write_perm()
def rename_studio_file(frappe_app: str, studio_app: str, file_path: str, new_path: str) -> dict:
	"""Rename/move an editable file or a folder within the app folder."""
	_validate_studio_file_access()
	source = _resolve_studio_file(frappe_app, studio_app, file_path)
	destination = _resolve_studio_file(frappe_app, studio_app, new_path)
	if not os.path.exists(source):
		frappe.throw(_("Not found: {0}").format(file_path))
	if os.path.exists(destination):
		frappe.throw(_("{0} already exists.").format(new_path))

	# files keep the editable-extension restriction; folders may be renamed freely, except the ones
	# the export manages (pages/components)
	if os.path.isfile(source):
		_validate_allowed_extension(file_path)
		_validate_allowed_extension(new_path)
		_validate_editable(studio_app, file_path)
	else:
		_validate_folder_removable(file_path)

	os.makedirs(os.path.dirname(destination), exist_ok=True)
	os.rename(source, destination)
	return {"path": new_path}


@frappe.whitelist()
@has_page_write_perm()
def delete_studio_file(frappe_app: str, studio_app: str, file_path: str) -> None:
	"""Delete an editable file, or a folder (with its contents), within the app folder."""
	_validate_studio_file_access()
	target = _resolve_studio_file(frappe_app, studio_app, file_path)
	if os.path.isdir(target):
		_validate_folder_removable(file_path)
		shutil.rmtree(target)
		return

	_validate_allowed_extension(file_path)
	_validate_editable(studio_app, file_path)
	if not os.path.isfile(target):
		frappe.throw(_("Not found: {0}").format(file_path))
	os.remove(target)


def _validate_studio_file_access() -> None:
	if not frappe.conf.developer_mode:
		frappe.throw(_("Editing Studio code files is only allowed in developer mode."))
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("You do not have permission to edit Studio code files."), frappe.PermissionError)


def _studio_app_root(frappe_app: str, studio_app: str) -> str:
	"""Absolute, symlink-resolved path of the app's studio folder (the jail root)."""
	return os.path.realpath(frappe.get_app_source_path(frappe_app, "studio", studio_app))


def _resolve_studio_file(frappe_app: str, studio_app: str, file_path: str) -> str:
	"""Resolve a path relative to the studio app root, refusing anything that escapes the jail."""
	root = _studio_app_root(frappe_app, studio_app)
	target = os.path.realpath(os.path.join(root, file_path))
	if target != root and not target.startswith(root + os.sep):
		frappe.throw(_("Invalid file path: {0}").format(file_path), frappe.PermissionError)
	return target


def _validate_allowed_extension(file_path: str) -> None:
	extension = os.path.splitext(file_path)[1].lower()
	if extension not in ALLOWED_STUDIO_FILE_EXTENSIONS:
		frappe.throw(_("Editing {0} files is not allowed.").format(extension or "these"))


def _is_export_doc_file(studio_app: str, file_path: str) -> bool:
	normalized = file_path.strip("/")
	if not normalized.lower().endswith(".json"):
		return False
	# pages/components live in their folders; the app itself exports to <scrub(app)>.json at the root
	return (
		normalized.startswith("studio_page/")
		or normalized.startswith("studio_components/")
		or normalized == f"{frappe.scrub(studio_app)}.json"
	)


def _is_export_folder(file_path: str) -> bool:
	normalized = file_path.strip("/")
	return normalized in ("studio_page", "studio_components") or bool(
		re.fullmatch(r"studio_page/[^/]+", normalized)
	)


def _validate_editable(studio_app: str, file_path: str) -> None:
	if _is_export_doc_file(studio_app, file_path):
		frappe.throw(_("{0} is generated by Studio and is read-only.").format(file_path))


def _validate_folder_removable(file_path: str) -> None:
	if _is_export_folder(file_path):
		frappe.throw(_("{0} is managed by Studio and can't be removed or renamed.").format(file_path))


def _file_hash(content: str) -> str:
	"""Short content fingerprint used to detect edits that happened on disk since the last read."""
	return hashlib.sha1(content.encode("utf-8")).hexdigest()


def _build_studio_file_tree(directory: str, root: str) -> list[dict]:
	"""Folders first (including empty ones, so newly created folders show up), then editable files;
	hidden/irrelevant entries skipped."""
	nodes = []
	for name in sorted(os.listdir(directory)):
		# tsconfig.json is auto-generated editor tooling (the @app/ alias), not app code
		if name.startswith(".") or name in ("__pycache__", "node_modules", "tsconfig.json"):
			continue

		absolute_path = os.path.join(directory, name)
		relative_path = os.path.relpath(absolute_path, root)

		if os.path.isdir(absolute_path):
			children = _build_studio_file_tree(absolute_path, root)
			nodes.append({"label": name, "path": relative_path, "is_folder": True, "children": children})
		elif os.path.splitext(name)[1].lower() in ALLOWED_STUDIO_FILE_EXTENSIONS:
			nodes.append({"label": name, "path": relative_path, "is_folder": False, "children": []})

	nodes.sort(key=lambda node: (not node["is_folder"], node["label"].lower()))
	return nodes
