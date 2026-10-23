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


def get_app_file_path(app_folder: str) -> str:
	"""The folder keeps the app's name as-is, but its JSON is written scrubbed (`my-app/my_app.json`)."""
	return os.path.join(app_folder, f"{frappe.scrub(os.path.basename(app_folder))}.json")


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
