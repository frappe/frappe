import re

import frappe

from studio.utils import walk_blocks

GET_ICON_BINDING = re.compile(r"\{\{\s*getIcon\(['\"]([a-z0-9-]+)['\"]\)\s*\}\}")


def execute():
	for page in frappe.get_all("Studio Page", fields=["name", "blocks", "draft_blocks"]):
		updates = {
			field: migrated
			for field in ("blocks", "draft_blocks")
			if page.get(field) and (migrated := migrate_blocks_json(page.get(field))) != page.get(field)
		}
		if updates:
			frappe.db.set_value("Studio Page", page.name, updates, update_modified=False)

	for component in frappe.get_all("Studio Component", fields=["name", "block"]):
		if component.block and (migrated := migrate_blocks_json(component.block)) != component.block:
			frappe.db.set_value("Studio Component", component.name, "block", migrated, update_modified=False)


def migrate_blocks_json(value):
	if "getIcon" not in value:
		return value
	blocks = frappe.parse_json(value)
	for block in walk_blocks(blocks):
		if block.get("componentProps"):
			block["componentProps"] = to_lucide_classes(block["componentProps"])
	return frappe.as_json(blocks, indent=None)


def to_lucide_classes(value):
	if isinstance(value, dict):
		return {key: to_lucide_classes(item) for key, item in value.items()}
	if isinstance(value, list):
		return [to_lucide_classes(item) for item in value]
	if isinstance(value, str) and (match := GET_ICON_BINDING.fullmatch(value.strip())):
		return f"lucide-{match.group(1)}"
	return value
