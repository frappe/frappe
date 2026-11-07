import json
import os
import re
from functools import wraps

import frappe


def camel_case_to_kebab_case(text, remove_spaces=False):
	if not text:
		return ""
	text = re.sub(r"(?<!^)(?=[A-Z])", "-", text).lower()
	if remove_spaces:
		text = text.replace(" ", "")
	return text


def walk_blocks(blocks):
	"""Yield all blocks recursively, including children and slots."""
	if isinstance(blocks, str):
		blocks = frappe.parse_json(blocks or "[]")
	if isinstance(blocks, dict):
		blocks = [blocks]

	stack = list(blocks or [])
	while stack:
		block = stack.pop()
		if not isinstance(block, dict):
			continue
		yield block
		stack.extend(block.get("children") or [])
		for slot in (block.get("componentSlots") or {}).values():
			content = slot.get("slotContent") if isinstance(slot, dict) else None
			if isinstance(content, list):
				stack.extend(content)


def has_page_write_perm(message: str | None = None):
	"""Decorator to check if user has permission to edit Studio Page.

	Args:
	        message: Custom error message to display if permission is denied.
	                 If not provided, defaults to "You do not have permission to modify pages"
	"""

	def decorator(fn):
		@wraps(fn)
		def wrapper(*args, **kwargs):
			if not frappe.has_permission("Studio Page", ptype="write"):
				error_message = message or frappe._("You do not have permission to modify pages")
				frappe.throw(error_message)
			return fn(*args, **kwargs)

		return wrapper

	return decorator


def validate_app_viewer_access(app_name: str, allow_guest_pages: bool = False) -> None:
	"""Check whether the current session may read an app's source files.

	Studio Page readers can preview unpublished apps. Other logged-in users need a
	published page. Guests also need `allow_guest_pages` and a published guest page.
	"""
	if frappe.has_permission("Studio Page", ptype="read"):
		return
	is_guest = frappe.session.user == "Guest"
	if is_guest and not allow_guest_pages:
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	page_filters = {"studio_app": app_name, "published": 1}
	if is_guest:
		page_filters["allow_guest"] = 1
	if not frappe.db.exists("Studio Page", page_filters):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)


def get_studio_folder(frappe_app: str) -> str:
	return frappe.get_app_source_path(frappe_app, "studio")


def get_export_folder(frappe_app: str, app_name: str) -> str:
	"""`my-app` exports to `studio/my_app` — app source folders carry scrubbed names, like a doctype's."""
	return os.path.join(get_studio_folder(frappe_app), frappe.scrub(app_name))


def get_app_file_path(app_folder: str) -> str:
	"""The folder and its app JSON both carry the scrubbed name (`my-app` exports to `my_app/my_app.json`)."""
	return os.path.join(app_folder, f"{frappe.scrub(os.path.basename(app_folder))}.json")


def script_extension(folder: str, stem: str, default: str = "ts") -> str:
	"""Return an existing script file's extension, or `default` for a new file."""
	for extension in ("ts", "js"):
		if os.path.isfile(os.path.join(folder, f"{stem}.{extension}")):
			return extension
	return default


def validate_one_script_file(folder: str, filename: str, moved_from: str | None = None) -> None:
	"""Reject a file whose companion in the other language exists, such as `board.ts` beside
	`board.js`. `moved_from` is the path a rename frees, so a file can switch language.

	Call it where a user or an agent writes a file, never where Studio reads one: discovery and
	builds must not fail over a file they do not use.
	"""
	stem, extension = os.path.splitext(filename)
	companion = {".ts": ".js", ".js": ".ts"}.get(extension)
	if not companion:
		return
	path = os.path.join(folder, stem + companion)
	if path != moved_from and os.path.isfile(path):
		frappe.throw(
			frappe._("{0} already has a {1} file. Keep only one script file.").format(stem, companion),
			title=frappe._("Ambiguous Script"),
		)


def find_script_file(folder: str, stem: str) -> str:
	return os.path.join(folder, f"{stem}.{script_extension(folder, stem)}")


def get_exported_app_name(app_folder: str) -> str:
	"""The app's name from its exported JSON. The folder name is scrubbed
	(`my-app` lives in `my_app`), so it cannot name the app."""
	name = json.loads(frappe.read_file(get_app_file_path(app_folder))).get("name")
	return name or os.path.basename(app_folder)


def validate_installed_app(app_name: str) -> None:
	"""`frappe.get_app_source_path` resolves any importable module, so only accept real apps."""
	if app_name not in frappe.get_installed_apps():
		frappe.throw(
			frappe._("App {0} is not installed on this site.").format(app_name),
			title=frappe._("Invalid App"),
		)


def validate_file_name(value: str, message: str, title: str | None = None) -> None:
	"""Refuse a name that cannot stay one folder or file name in an export path. Only path
	structure is checked, so ordinary title punctuation remains allowed."""
	if not value or value in (".", "..") or "/" in value or "\\" in value:
		frappe.throw(message, title=title)


def get_exported_app_folders(studio_folder: str) -> list[str]:
	"""Subfolders of `<app>/studio` that hold their app JSON. Anything else in there, like the
	editor in frappe's `studio/frontend`, is not a studio app."""
	if not os.path.isdir(studio_folder):
		return []
	folders = [os.path.join(studio_folder, entry) for entry in sorted(os.listdir(studio_folder))]
	return [folder for folder in folders if os.path.isfile(get_app_file_path(folder))]
