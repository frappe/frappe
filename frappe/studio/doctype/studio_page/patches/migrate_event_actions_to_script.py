import json

import frappe


def execute():
	"""Migrate the removed "Switch App Page" and "Open Webpage" event actions to "Run Script".

	These built-in actions were dropped in favour of scripts, so existing events are
	rewritten to equivalent router.push / window.open calls.
	"""
	Page = frappe.qb.DocType("Studio Page")
	pages = (
		frappe.qb.from_(Page)
		.select(Page.name, Page.blocks, Page.draft_blocks)
		.where(
			Page.blocks.like("%Switch App Page%")
			| Page.draft_blocks.like("%Switch App Page%")
			| Page.blocks.like("%Open Webpage%")
			| Page.draft_blocks.like("%Open Webpage%")
		)
		.run(as_dict=True)
	)

	for page in {p.name: p for p in pages}.values():
		updates = {}
		for field in ("blocks", "draft_blocks"):
			blocks = frappe.parse_json(page.get(field) or "[]")
			if blocks and migrate_blocks(blocks):
				updates[field] = frappe.as_json(blocks)
		if updates:
			frappe.get_doc("Studio Page", page.name).update(updates).save()

	components = frappe.get_all("Studio Component", fields=["name", "block"])
	for component in components:
		if not component.get("block"):
			continue
		block = frappe.parse_json(component.get("block"))
		if migrate_blocks([block]):
			frappe.get_doc("Studio Component", component.name).update({"block": frappe.as_json(block)}).save()


def migrate_blocks(blocks):
	"""Recursively rewrite legacy event actions. Returns True if anything changed."""
	changed = False
	for block in blocks:
		for event in (block.get("componentEvents") or {}).values():
			if migrate_event(event):
				changed = True

		if block.get("children"):
			changed = migrate_blocks(block["children"]) or changed

		for slot in (block.get("componentSlots") or {}).values():
			content = slot.get("slotContent") if slot else None
			if isinstance(content, list):
				changed = migrate_blocks(content) or changed

	return changed


def migrate_event(event):
	action = event.get("action")
	if action == "Switch App Page":
		event["script"] = f"router.push({json.dumps(event.get('page') or '')})"
	elif action == "Open Webpage":
		event["script"] = f"window.open({json.dumps(event.get('url') or '')})"
	else:
		return False

	event["action"] = "Run Script"
	event.pop("page", None)
	event.pop("url", None)
	return True
