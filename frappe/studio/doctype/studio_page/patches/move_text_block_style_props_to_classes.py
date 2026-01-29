import frappe


def execute():
	"""move text block style props to classes"""

	pages = frappe.get_all(
		"Studio Page",
		or_filters={
			"blocks": ["like", "%TextBlock%"],
			"draft_blocks": ["like", "%TextBlock%"],
		},
		fields=["name", "blocks", "draft_blocks"],
	)
	for page in pages:
		blocks = frappe.parse_json(page.get("blocks") or "[]")
		draft_blocks = frappe.parse_json(page.get("draft_blocks") or "[]")

		if blocks:
			updated_blocks = move_style_props_to_classes(blocks)
			frappe.db.set_value(
				"Studio Page",
				page.name,
				{"blocks": frappe.as_json(updated_blocks)},
				update_modified=False,
			)
		if draft_blocks:
			updated_draft_blocks = move_style_props_to_classes(draft_blocks)
			frappe.db.set_value(
				"Studio Page",
				page.name,
				{"draft_blocks": frappe.as_json(updated_draft_blocks)},
				update_modified=False,
			)

	components = frappe.get_all("Studio Component", fields=["name", "block"])
	for component in components:
		if not component.get("block"):
			continue
		block = frappe.parse_json(component.get("block"))
		updated_block = move_style_props_to_classes([block])[0]
		frappe.db.set_value(
			"Studio Component",
			component.name,
			{"block": frappe.as_json(updated_block)},
			update_modified=False,
		)


def move_style_props_to_classes(blocks):
	for block in blocks:
		if block.get("componentName") == "TextBlock":
			props = block.get("componentProps", {})
			classes = block.get("classes", [])
			classes = set(classes)

			prop_names = ["fontWeight", "lineHeight", "textColor"]
			for prop in prop_names:
				if prop in props:
					value = props.get(prop)
					if value:
						classes.add(value)

			block["classes"] = list(classes)
		if block.get("children"):
			block["children"] = move_style_props_to_classes(block["children"])
		if block.get("componentSlots"):
			for slot in block["componentSlots"].values():
				if slot and slot.get("slotContent") and isinstance(slot["slotContent"], list):
					slot["slotContent"] = move_style_props_to_classes(slot["slotContent"])

	return blocks
