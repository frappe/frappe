"""Slots now hold blocks only — string/HTML slot content is no longer rendered.

Convert every leftover string into an equivalent block so existing pages keep their
content: markup becomes an HTML block, plain text a TextBlock.
"""

import re

import frappe

HTML_PATTERN = re.compile(r"<[a-z][\s\S]*>", re.IGNORECASE)


def execute():
	pages = frappe.get_all("Studio Page", fields=["name", "blocks", "draft_blocks"])
	for page in pages:
		updates = {}
		for field in ("blocks", "draft_blocks"):
			blocks = frappe.parse_json(page.get(field) or "[]")
			if blocks and migrate_blocks(blocks):
				updates[field] = frappe.as_json(blocks)
		if updates:
			frappe.get_doc("Studio Page", page.name).update(updates).save()

	components = frappe.get_all("Studio Component", fields=["name", "block"])
	for component in components:
		block = frappe.parse_json(component.get("block") or "{}")
		if block and migrate_blocks([block]):
			frappe.get_doc("Studio Component", component.name).update({"block": frappe.as_json(block)}).save()


def migrate_blocks(blocks) -> bool:
	"""Rewrite string slot content in place. Returns True if anything changed."""
	migrated = False
	for block in blocks:
		if not isinstance(block, dict):
			continue

		for slot_name, slot in (block.get("componentSlots") or {}).items():
			content = slot.get("slotContent") if isinstance(slot, dict) else None
			if isinstance(content, list):
				migrated = migrate_blocks(content) or migrated
			elif isinstance(content, str):
				slot["slotContent"] = as_blocks(content, slot_name)
				migrated = True

		migrated = migrate_blocks(block.get("children") or []) or migrated

	return migrated


def as_blocks(content: str, slot_name: str) -> list[dict]:
	if not content.strip():
		return []

	if HTML_PATTERN.search(content):
		component_name, props = "HTML", {"html": content}
	else:
		component_name, props = "TextBlock", {"text": content, "tag": "p"}

	return [
		{
			"componentId": f"{component_name}-{frappe.generate_hash(length=9)}",
			"componentName": component_name,
			"componentProps": props,
			"children": [],
			"parentSlotName": slot_name,
		}
	]
