"""Replace complete icon bindings and report JavaScript references for manual migration."""

import re

import frappe

from studio.utils import walk_blocks

GET_ICON_BINDING = re.compile(r"\{\{\s*getIcon\s*\(\s*(['\"])([a-z0-9-]+)\1\s*\)\s*\}\}")
# These are candidates for review, including method calls, strings and comments.
GET_ICON_REFERENCE = re.compile(r"(?<![\w$])getIcon(?![\w$])(?:\s*\([^)]*\))?")

FIELDS = {"Studio Page": ("script", "blocks", "draft_blocks"), "Studio Component": ("block",)}


def execute():
	unresolved = []
	for doctype, fields in FIELDS.items():
		for doc in frappe.get_all(doctype, fields=["name", *fields]):
			updates = {}
			for field in fields:
				if not doc.get(field) or "getIcon" not in doc[field]:
					continue
				text = rewrite_get_icon_calls(doc[field], is_script=field == "script")
				if text != doc[field]:
					updates[field] = text
				unresolved.extend((f"{doc.name}.{field}", call) for call in find_get_icon_calls(text))
			if updates:
				frappe.db.set_value(doctype, doc.name, updates, update_modified=False)

	if unresolved:
		print(
			"Review remaining getIcon references; replace calls to Studio's removed helper with lucide-* strings:\n"
			+ "\n".join(f"  {name}: {call}" for name, call in sorted(set(unresolved)))
		)


def rewrite_get_icon_calls(text: str, *, is_script: bool = False) -> str:
	# Regex replacements in JavaScript can corrupt methods, strings and comments.
	if is_script or "getIcon" not in text:
		return text
	blocks = frappe.parse_json(text)
	changed = False
	for block in walk_blocks(blocks):
		props = block.get("componentProps")
		updated = rewrite_bindings(props)
		if updated != props:
			block["componentProps"] = updated
			changed = True
	return frappe.as_json(blocks, indent=None) if changed else text


def rewrite_bindings(value):
	if isinstance(value, dict):
		return {key: rewrite_bindings(item) for key, item in value.items()}
	if isinstance(value, list):
		return [rewrite_bindings(item) for item in value]
	if isinstance(value, str) and (match := GET_ICON_BINDING.fullmatch(value)):
		return lucide_class(match.group(2))
	return value


def find_get_icon_calls(text: str) -> list[str]:
	return GET_ICON_REFERENCE.findall(text)


def lucide_class(name: str) -> str:
	return name if name.startswith("lucide-") else f"lucide-{name}"
