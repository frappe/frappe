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
			content = slot.get("slotContent")
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
