import frappe

OPTIONS_KEYS = ("title", "message", "size", "icon", "actions", "position", "paddingTop")

SLOT_RENAMES = {
	"body-content": "default",
	"body-title": "title",
	"body": "default",
}


def execute():
	pages = frappe.get_all(
		"Studio Page",
		or_filters={
			"blocks": ["like", "%Dialog%"],
			"draft_blocks": ["like", "%Dialog%"],
		},
		fields=["name", "blocks", "draft_blocks"],
	)
	for page in pages:
		updates = {}
		for field in ("blocks", "draft_blocks"):
			blocks = frappe.parse_json(page.get(field) or "[]")
			if blocks:
				updates[field] = frappe.as_json(migrate_dialog_blocks(blocks))
		if updates:
			frappe.db.set_value("Studio Page", page.name, updates, update_modified=False)

	components = frappe.get_all(
		"Studio Component",
		filters={"block": ["like", "%Dialog%"]},
		fields=["name", "block"],
	)
	for component in components:
		if not component.get("block"):
			continue
		block = frappe.parse_json(component.get("block"))
		updated_block = migrate_dialog_blocks([block])[0]
		frappe.db.set_value(
			"Studio Component",
			component.name,
			{"block": frappe.as_json(updated_block)},
			update_modified=False,
		)


def migrate_dialog_blocks(blocks):
	for block in blocks:
		if block.get("componentName") == "Dialog":
			migrate_dialog_props(block)
			rename_dialog_slots(block)

		if block.get("children"):
			block["children"] = migrate_dialog_blocks(block["children"])

		for slot in (block.get("componentSlots") or {}).values():
			if slot and isinstance(slot.get("slotContent"), list):
				slot["slotContent"] = migrate_dialog_blocks(slot["slotContent"])

	return blocks


def migrate_dialog_props(block):
	props = block.get("componentProps") or {}

	# 1. flatten the `options` blob into top-level props (existing top-level wins)
	options = props.pop("options", None)
	if isinstance(options, dict):
		for key in OPTIONS_KEYS:
			if key in options and key not in props:
				props[key] = options[key]

	# 2. legacy `#body` was a full layout override -> v1 `bare` + default slot
	if "body" in block.get("componentSlots", {}):
		props.setdefault("bare", True)

	# 3. `disableOutsideClickToClose` -> `dismissible` (inverted)
	if "disableOutsideClickToClose" in props:
		disabled = props.pop("disableOutsideClickToClose")
		props.setdefault("dismissible", not disabled)

	block["componentProps"] = props


def rename_dialog_slots(block):
	slots = block.get("componentSlots")
	if not slots:
		return

	for legacy_name, new_name in SLOT_RENAMES.items():
		if legacy_name not in slots or new_name in slots:
			continue

		slot = slots.pop(legacy_name, None)
		slot["slotName"] = new_name
		# slotId is `componentId:slotName` -> keep the componentId, swap the suffix
		if slot.get("slotId"):
			component_id = slot["slotId"].rsplit(":", 1)[0]
			slot["slotId"] = f"{component_id}:{new_name}"
		# child blocks point back at the slot via `parentSlotName` -> keep in sync
		if isinstance(slot.get("slotContent"), list):
			for child in slot["slotContent"]:
				if child.get("parentSlotName") == legacy_name:
					child["parentSlotName"] = new_name
		slots[new_name] = slot
