"""`getIcon()` is gone: rewrite its literal calls in scripts and blocks to the lucide class it returned."""

import re

import frappe

# a whole-value binding becomes the bare class the icon picker understands
GET_ICON_BINDING = re.compile(r"\{\{\s*getIcon\(\s*\\?['\"]([a-z0-9-]+)\\?['\"]\s*\)\s*\}\}")
# any other literal call (page script, event handler, expression) becomes a string literal
GET_ICON_CALL = re.compile(r"getIcon\(\s*(\\?['\"])([a-z0-9-]+)\1\s*\)")
DYNAMIC_CALL = re.compile(r"getIcon\([^)]*\)")

FIELDS = {"Studio Page": ("script", "blocks", "draft_blocks"), "Studio Component": ("block",)}


def execute():
	dynamic = []
	for doctype, fields in FIELDS.items():
		for doc in frappe.get_all(doctype, fields=["name", *fields]):
			updates = {}
			for field in fields:
				if not doc.get(field) or "getIcon(" not in doc[field]:
					continue
				updates[field] = rewrite_get_icon_calls(doc[field])
				dynamic.extend((doc.name, call) for call in DYNAMIC_CALL.findall(updates[field]))
			if updates:
				frappe.db.set_value(doctype, doc.name, updates, update_modified=False)

	if dynamic:
		print(
			"getIcon() calls with a dynamic argument need a manual rewrite to a lucide-* string:\n"
			+ "\n".join(f"  {name}: {call}" for name, call in sorted(set(dynamic)))
		)


def rewrite_get_icon_calls(text: str) -> str:
	text = GET_ICON_BINDING.sub(lambda m: lucide_class(m.group(1)), text)
	return GET_ICON_CALL.sub(lambda m: f"{m.group(1)}{lucide_class(m.group(2))}{m.group(1)}", text)


def lucide_class(name: str) -> str:
	return name if name.startswith("lucide-") else f"lucide-{name}"
