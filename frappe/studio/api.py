import os
import shutil
from typing import Literal

import frappe
from frappe import _
from frappe.model import child_table_fields, display_fieldtypes, no_value_fields, std_fields, table_fields
from frappe.studio import files
from frappe.studio.constants import STANDARD_COMPONENT_NAMES
from frappe.studio.files import (
	ALLOWED_STORED_FILE_EXTENSIONS,
	ALLOWED_STUDIO_FILE_EXTENSIONS,
	file_hash,
	validate_allowed_extension,
	validate_editable,
	validate_folder_removable,
)
from frappe.studio.utils import (
	find_script_file,
	get_export_folder,
	get_exported_app_folders,
	get_studio_folder,
	has_page_write_perm,
	validate_app_viewer_access,
	validate_installed_app,
)
from frappe.utils import sbool


@frappe.whitelist()
def get_app_boot(app_name: str) -> dict:
	app = frappe.get_doc("Studio App", app_name)
	app.check_permission("read")
	return app.get_boot()


@frappe.whitelist()
def get_doctype_fields(doctype: str, with_standard_fields: bool = False) -> list[dict]:
	frappe.has_permission(doctype, ptype="read", throw=True)
	excluded_fieldtypes = (set(no_value_fields) | set(display_fieldtypes)) - set(table_fields)
	fields = [
		field for field in frappe.get_meta(doctype).fields if field.fieldtype not in excluded_fieldtypes
	]
	standard_fields = [frappe._dict(fieldname="name", fieldtype="Data", label="ID")]
	if sbool(with_standard_fields):
		standard_fields += get_meta_fields(doctype)

	existing_fieldnames = {field.fieldname for field in fields}
	fields += [field for field in standard_fields if field.fieldname not in existing_fieldnames]
	return fields


def get_meta_fields(doctype: str) -> list[frappe._dict]:
	"""Standard columns every document table has, plus parent columns for child tables"""
	fields = [frappe._dict(field) for field in std_fields if field["fieldname"] != "name"]
	if frappe.get_meta(doctype).istable:
		fields += [frappe._dict(fieldname=fieldname, fieldtype="Data") for fieldname in child_table_fields]
	return fields


@frappe.whitelist()
def get_whitelisted_methods(doctype: str) -> list[str]:
	from frappe import is_whitelisted
	from frappe.model.base_document import get_controller

	frappe.has_permission(doctype, ptype="read", throw=True)
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
	frappe.has_permission(doctype, ptype="read", throw=True)
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


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def get_custom_vue_components(frappe_app: str, studio_app: str) -> list[dict]:
	"""List the custom Vue SFC components one studio app exports, from the folder the build reads.

	Only a repository app ships them. Require Studio Page read permission, because
	their metadata includes server file paths.
	"""
	frappe.has_permission("Studio Page", ptype="read", throw=True)
	validate_installed_app(frappe_app)
	components = []
	seen_names = set()

	app_folder = get_export_folder(frappe_app, studio_app)
	if app_folder not in get_exported_app_folders(get_studio_folder(frappe_app)):
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

	for dirpath, _dirnames, filenames in os.walk(app_folder):
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
					"studio_file_path": os.path.relpath(file_path, app_folder),
				}
			)

	return components


@frappe.whitelist()
def get_studio_page_scripts(frappe_app: str) -> list[dict]:
	"""Discover exported page scripts (<page>.js) under <app>/studio/<studio_app>/studio_page/.

	Keyed by the page's docname (`page_name`, read from the sibling JSON) so the runtime can load
	a page's compiled setup() module by its docname.
	"""
	validate_installed_app(frappe_app)
	scripts = []

	studio_folder = get_studio_folder(frappe_app)
	if not os.path.exists(studio_folder):
		return []

	for studio_app in sorted(os.listdir(studio_folder)):
		page_folder = os.path.join(studio_folder, studio_app, "studio_page")
		if not os.path.isdir(page_folder):
			continue

		# each page is a folder holding <stem>.json + <stem>.js
		for entry in sorted(os.listdir(page_folder)):
			page_dir = os.path.join(page_folder, entry)
			if not os.path.isdir(page_dir):
				continue

			file_path = find_script_file(page_dir, entry)
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
# The file APIs support both source stores. Repository files are under `studio/<studio_app>/`
# and require developer mode. Database files use `frappe.studio.files` and can be edited
# without a repository or developer mode. Both paths check app permissions.
# ---------------------------------------------------------------------------


@frappe.whitelist()
def list_studio_files(frappe_app: str, studio_app: str) -> list[dict]:
	"""Return the app's editable file tree."""
	if files.uses_db_files(studio_app):
		_validate_studio_file_access(on_disk=False)
		return files.list_store_tree(studio_app)

	_validate_studio_file_access()
	root = _studio_app_root(frappe_app, studio_app)
	if not os.path.isdir(root):
		return []
	return _build_studio_file_tree(root, root)


@frappe.whitelist()
def read_studio_file(frappe_app: str, studio_app: str, file_path: str, ignore_missing: bool = False) -> dict:
	"""Return a file's content plus a hash callers pass back to write_studio_file for conflict checks."""
	if files.uses_db_files(studio_app):
		_validate_studio_file_access(on_disk=False)
		validate_allowed_extension(file_path, ALLOWED_STORED_FILE_EXTENSIONS)
		content = files.read_store_file(studio_app, file_path)
		if content is None:
			if sbool(ignore_missing):
				return {"path": file_path, "content": None, "hash": None}
			frappe.throw(_("File not found: {0}").format(file_path))
		return {"path": file_path, "content": content, "hash": file_hash(content)}

	_validate_studio_file_access()
	validate_allowed_extension(file_path)
	target = _resolve_studio_file(frappe_app, studio_app, file_path)
	if not os.path.isfile(target):
		if sbool(ignore_missing):
			return {"path": file_path, "content": None, "hash": None}
		frappe.throw(_("File not found: {0}").format(file_path))

	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(target, encoding="utf-8") as f:
		content = f.read()
	return {"path": file_path, "content": content, "hash": file_hash(content)}


@frappe.whitelist()
@has_page_write_perm()
def write_studio_file(
	frappe_app: str, studio_app: str, file_path: str, content: str, known_hash: str | None = None
) -> dict:
	"""Write a file and create any required parent folders.

	If `known_hash` is supplied, reject the write when the existing content has changed.
	"""
	if files.uses_db_files(studio_app):
		_validate_studio_file_access("write", on_disk=False)
		files.write_store_file(studio_app, file_path, content, known_hash)
		return {"path": file_path, "hash": file_hash(content)}

	_validate_studio_file_access("write")
	validate_allowed_extension(file_path)
	validate_editable(studio_app, file_path)
	target = _resolve_studio_file(frappe_app, studio_app, file_path)

	if known_hash and os.path.isfile(target):
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(target, encoding="utf-8") as f:
			if file_hash(f.read()) != known_hash:
				frappe.throw(_("{0} changed on disk since you opened it.").format(file_path))

	os.makedirs(os.path.dirname(target), exist_ok=True)
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(target, "w", encoding="utf-8") as f:
		f.write(content)
	return {"path": file_path, "hash": file_hash(content)}


@frappe.whitelist()
@has_page_write_perm()
def create_studio_file(frappe_app: str, studio_app: str, file_path: str) -> dict:
	"""Create an empty editable file (and any parent folders); error if it already exists."""
	if files.uses_db_files(studio_app):
		_validate_studio_file_access("write", on_disk=False)
		files.create_store_file(studio_app, file_path)
		return {"path": file_path, "hash": file_hash("")}

	_validate_studio_file_access("write")
	validate_allowed_extension(file_path)
	validate_editable(studio_app, file_path)
	target = _resolve_studio_file(frappe_app, studio_app, file_path)
	if os.path.exists(target):
		frappe.throw(_("{0} already exists.").format(file_path))

	os.makedirs(os.path.dirname(target), exist_ok=True)
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(target, "w", encoding="utf-8") as f:
		f.write("")
	return {"path": file_path, "hash": file_hash("")}


@frappe.whitelist()
@has_page_write_perm()
def create_studio_folder(frappe_app: str, studio_app: str, folder_path: str) -> dict:
	"""Create an empty folder (and any parent folders) in a repository app's folder."""
	if files.uses_db_files(studio_app):
		frappe.throw(_("A folder appears when you create a file in it."))

	_validate_studio_file_access("write")
	target = _resolve_studio_file(frappe_app, studio_app, folder_path)
	if os.path.exists(target):
		frappe.throw(_("{0} already exists.").format(folder_path))
	os.makedirs(target)
	return {"path": folder_path}


@frappe.whitelist()
@has_page_write_perm()
def rename_studio_file(frappe_app: str, studio_app: str, file_path: str, new_path: str) -> dict:
	"""Rename/move an editable file or a folder within the app folder."""
	if files.uses_db_files(studio_app):
		_validate_studio_file_access("write", on_disk=False)
		files.rename_store_path(studio_app, file_path, new_path)
		return {"path": new_path}

	_validate_studio_file_access("write")
	source = _resolve_studio_file(frappe_app, studio_app, file_path)
	destination = _resolve_studio_file(frappe_app, studio_app, new_path)
	if not os.path.exists(source):
		frappe.throw(_("Not found: {0}").format(file_path))
	if os.path.exists(destination):
		frappe.throw(_("{0} already exists.").format(new_path))

	# files keep the editable-extension restriction; folders may be renamed freely, except the ones
	# the export manages (pages/components)
	if os.path.isfile(source):
		validate_allowed_extension(file_path)
		validate_allowed_extension(new_path)
		validate_editable(studio_app, file_path)
		validate_editable(studio_app, new_path)
	else:
		validate_folder_removable(file_path)

	os.makedirs(os.path.dirname(destination), exist_ok=True)
	os.rename(source, destination)
	return {"path": new_path}


@frappe.whitelist()
@has_page_write_perm()
def delete_studio_file(frappe_app: str, studio_app: str, file_path: str) -> None:
	"""Delete an editable file, or a folder (with its contents), within the app folder."""
	if files.uses_db_files(studio_app):
		_validate_studio_file_access("write", on_disk=False)
		files.delete_store_path(studio_app, file_path)
		return

	_validate_studio_file_access("write")
	target = _resolve_studio_file(frappe_app, studio_app, file_path)
	if os.path.isdir(target):
		validate_folder_removable(file_path)
		shutil.rmtree(target)
		return

	validate_allowed_extension(file_path)
	validate_editable(studio_app, file_path)
	if not os.path.isfile(target):
		frappe.throw(_("Not found: {0}").format(file_path))
	os.remove(target)


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def get_app_files(app_name: str) -> list[dict]:
	"""Return a database app's source files for compilation in the browser.

	Use the same viewer permissions as `get_page`. Users with Studio Page read
	permission can preview unpublished apps. Other logged-in users need a published
	page; guests need a published page that allows guests. Resource endpoints check
	permissions separately when the app requests business data.
	"""
	if not isinstance(app_name, str):
		frappe.throw(_("Invalid app name."))
	validate_app_viewer_access(app_name, allow_guest_pages=True)
	if not files.uses_db_files(app_name):
		return []
	return files.get_store_files(app_name)


def _validate_studio_file_access(permission_type: str = "read", on_disk: bool = True) -> None:
	"""Check Studio App permissions and require developer mode for files on disk."""
	if on_disk and not frappe.conf.developer_mode:
		frappe.throw(_("Editing Studio code files is only allowed in developer mode."))
	frappe.has_permission("Studio App", ptype=permission_type, throw=True)


def _studio_app_root(frappe_app: str, studio_app: str) -> str:
	"""Absolute, symlink-resolved path of the app's studio folder (the jail root)."""
	if frappe.db.get_value("Studio App", studio_app, "frappe_app") != frappe_app:
		frappe.throw(
			_("Studio App {0} is not exported to {1}.").format(studio_app, frappe_app), frappe.PermissionError
		)
	return os.path.realpath(get_export_folder(frappe_app, studio_app))


def _resolve_studio_file(frappe_app: str, studio_app: str, file_path: str) -> str:
	"""Resolve a path relative to the studio app root, refusing anything that escapes the jail."""
	root = _studio_app_root(frappe_app, studio_app)
	target = os.path.realpath(os.path.join(root, file_path))
	if target != root and not target.startswith(root + os.sep):
		frappe.throw(_("Invalid file path: {0}").format(file_path), frappe.PermissionError)
	return target


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
